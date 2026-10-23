# Friction Log

Real problems hit while building Serion, in the order they came up. Each one changed a design decision, not just a line of code.

---

## 1. Gemini model deprecated mid-build, with no warning in the docs

**What happened:** `gemini-2.5-flash` worked on day one. On the next run, every call failed with a `NOT_FOUND` error.

**Root cause:** Google had retired the model for new API keys. The only place this was discoverable was the error message itself:

> *"This model models/gemini-2.5-flash is no longer available to new users. Please update your code to use models/gemini-3.8-flash."*

**Fix:** Swapped the model id. One line.

**Takeaway:** For a hackathon running on a free-tier key created the same week, model availability isn't a one-time setup decision — it's something that can change under you mid-build. Worth building retries and clear error surfacing from day one, not as an afterthought.

---

## 2. A retried network call silently tripled a real payment claim

**What happened:** After adding retry logic for transient `ServerError`s, a single message — *"Ben paid Ana 50"* — resulted in **three separate claims** being logged, not one.

**Root cause:** The retry wrapper re-sent the entire user message as a brand-new conversational turn on failure. The agent had no way to know "this is a retry of the same request" — from its perspective, the user had just said "Ben paid Ana 50" again, so it reasonably called `log_payment` again. Two retries on the first message meant two extra, real database writes.

**Fix:** Rather than trying to solve this at the retry/network layer (hard to do correctly), fixed it at the data layer: `log_payment_claim` now checks for an identical claim (same payer, receiver, amount) logged in the last 30 seconds, and returns that existing claim instead of creating a new one.

**Takeaway:** This is exactly the kind of bug that matters most for a trust-focused app. A network hiccup should never be able to duplicate a financial record. The fix is also arguably a *better* design independent of the bug — it protects against a person genuinely repeating themselves by voice, not just against retry replay.

---

## 3. Two independent retry layers were stacking without either one knowing

**What happened:** A single failed message sometimes took over a minute to return anything — far longer than the app's own retry settings should have allowed.

**Root cause:** Google's `google-genai` SDK does its own internal retrying with exponential backoff *before* raising an error back to the caller. The app's own retry wrapper then retried *on top of that* — two retry layers compounding, invisibly.

**Fix:** Took explicit control: disabled the SDK's internal retrying (`retry_options=HttpRetryOptions(attempts=1)`) and set a hard 20-second timeout per request, so a single call either succeeds or fails fast — and the app's own visible retry loop (with on-screen "retrying in Xs..." messages) handles all the waiting instead.

**Takeaway:** When a library claims to "handle retries for you," it's worth checking whether that's actually documented behavior or an undocumented default — in this case, different sources disagreed on what the SDK did by default, which made the first fix (just adding more retries) actively worse.

---

## 4. "ServerError" and "ClientError" needed two completely different responses

**What happened:** A later failure returned a `ClientError` instead of the `ServerError` seen before — and the existing retry logic treated it identically, burning through retries that couldn't possibly help.

**Root cause:** `ClientError` meant a rate-limit or daily quota cap, not a temporary server issue. Retrying in seconds doesn't fix a quota cap; only waiting for a reset (or switching models) does.

**Fix:** Added detection for rate-limit-shaped errors specifically, failing fast with a message pointing to the actual usage dashboard instead of retrying blindly.

**Confirmed via the dashboard:** `aistudio.google.com/rate-limit` showed the real cause plainly — `gemini-3.8-flash` was at 42/20 requests for the day, well over its free-tier daily cap, while `gemini-3.5-flash-lite` sat at 44/500. Switched models rather than waiting for the reset.

**Takeaway:** Error *type* matters as much as error *presence*. The right response to "the server is briefly overloaded" and "you've used your daily quota" are opposites — one deserves a retry, the other deserves an immediate, clear stop.

---

## 5. No AWS account meant redesigning the model layer mid-project, not after

**What happened:** Completing AWS registration required a card capable of international billing. Without one readily available, Bedrock wasn't usable for the core build.

**Fix:** Rebuilt the plan around Gemini's free tier from day one, using the Strands SDK's model-agnostic design (the same pattern already proven on an earlier project) to swap providers without touching the agent's tool-calling architecture.

**Takeaway:** "Build with AWS" and "have a verified AWS account with billing" turned out to be two different bars to clear, and the second one has real-world friction (a working international card) that has nothing to do with engineering skill. Designing the model layer to be provider-agnostic from the start meant this constraint cost a redesign decision, not a stalled project.

---

## What these add up to

None of these were "we didn't know how to code X." Every one was a gap between how a tool or platform *claims* to behave and how it actually behaves under real conditions — stacked retries, silent model deprecation, ambiguous error types, and account-setup friction that has nothing to do with the actual build. Designing Serion's trust mechanism (confirmations, duplicate guards, partial-payment tracking) to be resilient to exactly this kind of unreliability turned out to be as central to the project as the ledger logic itself.
