"""
Serion's agent — the simulated Alexa+ brain.

This is what a real Alexa+ MCP server would expose as tools; here
it's a Strands agent running locally against Gemini, since that's
what you talk to in the demo.

Run with: python -m agent.agent
"""

import os
from dotenv import load_dotenv
from google.genai import types
from strands import Agent
from strands.models.gemini import GeminiModel

from agent.tools import (
    log_payment, confirm_payment, check_status, check_payout_forecast,
    open_ballot, cast_ballot, check_ballot_result, parse_receipt_text,
    explain_rule, cycle_report,
)

load_dotenv()

SYSTEM_PROMPT = """You are Serion, a voice-first treasurer for a savings circle.

Rules you must always follow:
- A payment is never real just because someone claims it. It stays
  pending until the RECEIVER confirms it themselves.
- Never let a payer confirm their own payment.
- If the receiver says they only got part of the claimed amount
  (e.g. "I only received 30 of the 50"), confirm with that smaller
  confirmed_amount — don't round up or treat it as a full confirm.
- Be concise — you're a voice assistant, not a chatbot. Keep replies
  to 1-3 short sentences unless listing claims.
- If a user pastes receipt-like text, parse it first, confirm the
  details with them, then log it.
- Ballots are private. NEVER reveal how a specific person voted,
  even if asked directly or asked by the person who voted. Only
  ever share the aggregate yes/no totals and the outcome.
- Messages may arrive prefixed like "[Speaking as Grace]". That
  tells you who is currently talking — interpret "I", "me", and
  "my" as referring to that person. Never say the prefix out loud
  or mention it in your reply.
"""


def build_agent():
    api_key = os.getenv("GEMINI_API_KEY")
    # Disable the SDK's own hidden retrying (attempts=1) and cap each
    # request at 20s, so a struggling request fails fast into our own
    # visible retry loop below instead of silently retrying for minutes.
    http_options = types.HttpOptions(
        timeout=20_000,
        retry_options=types.HttpRetryOptions(attempts=1),
    )
    model = GeminiModel(
        client_args={"api_key": api_key, "http_options": http_options},
        model_id="gemini-3.5-flash-lite",
    )
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[log_payment, confirm_payment, check_status, check_payout_forecast,
               open_ballot, cast_ballot, check_ballot_result, parse_receipt_text,
               explain_rule, cycle_report],
        callback_handler=None,  # we print our own output below
    )


def ask_with_retry(agent, message, attempts=3, base_wait=4):
    """
    Gemini's free tier occasionally returns a transient 503 under
    high demand — that's worth a few retries. A 429 rate-limit/quota
    error is different: retrying in seconds won't help, so we fail
    fast with a clear message instead of wasting time (and quota).
    """
    import time
    last_error = None
    for attempt in range(attempts):
        try:
            return str(agent(message))
        except Exception as e:
            last_error = e
            is_rate_limit = (
                "ClientError" in type(e).__name__
                or "429" in str(e)
                or "RESOURCE_EXHAUSTED" in str(e)
            )
            if is_rate_limit:
                return (
                    "(Hit a Gemini free-tier rate limit or daily quota cap — "
                    "retrying won't help right now. Check "
                    "https://aistudio.google.com/rate-limit for your current "
                    "usage. Daily quotas reset at midnight Pacific time.)"
                )
            if attempt < attempts - 1:
                wait = base_wait * (attempt + 1)
                print(f"   (model busy, retrying in {wait}s...)")
                time.sleep(wait)
    return (f"(Serion couldn't reach the model after several tries — "
            f"{type(last_error).__name__}. Gemini's free tier may be under "
            f"heavy load right now — wait a minute and try again.)")


if __name__ == "__main__":
    agent = build_agent()
    print("Serion is ready. Type a message, or 'quit' to exit.\n")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit"):
            break
        if not user_input:
            continue
        response = ask_with_retry(agent, user_input)
        print(f"Serion: {response}\n")
