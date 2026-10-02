# Serion
Serion is a voice-first "payment memory" for shared money — savings circles, SACCOs, chamas, roommates splitting rent, family funds
— built as a simulated Alexa+ experience for the [Build, Ship, Shape: Amazon Developer Hackathon](https://amazonappdev2026.devpost.com/).

> Built for the **Alexa+** track, with entries in the **AWS Builder** and **Open Source** mini-challenges.

## The Problem

Informal savings groups run on cash, mobile-money screenshots, and a treasurer's notebook. That makes three things hard to resolve fairly:
- **Did they actually pay?** — claims rest on someone's word
- **Can we cover the next payout?** — nobody can say with confidence until the day arrives
- **Can we vote on a loan without it getting awkward?** — votes happen out loud, in front of the person being voted on

## The Solution

Serion is a conversational agent that members talk to — by voice or text — to log payments, confirm what they've received, forecast upcoming payouts, and vote privately on requests. Nothing is "true" in the ledger until the *receiving* member confirms it from their own account, so trust comes from the system's design, not from memory or goodwill.

## Core Features

| Feature | What it does 
 **Voice/text payment logging**  State a payment in natural language; the agent extracts who paid, who received, and how much |
 **Receipt text ingestion**  Paste a transfer notification or receipt text; the agent parses and matches it to what's owed |
 **Two-sided confirmation**  A claimed payment stays *pending* until the receiver confirms it from their own profile |
 **Partial payment handling**  Short payments are logged as partial, with a tracked promise for the remainder |
 **Payout forecast**  "Can we cover Ana's payout Friday?" returns a probability with stated reasons |
 **Private ballots**  Loan and emergency requests go to anonymous voting — only the result is announced |
  **Rules as data**  The group's constitution (cycle length, late fine, loan cap, quorum) is stored and queryable by voice |
  **Cycle reports**  A plain-language summary of a completed contribution cycle |

## How It Works

Serion simulates an Alexa+-style experience: a conversational frontend backed by an agent that decides which tool to call based on what you say, 
executes it against a real ledger, and replies with a card-style result.

User (voice/text)
      │
      ▼
 Agent (Amazon Bedrock — Nova Lite / Claude Opus 5.5)
      │  decides which tool to call
      ▼
 Tool layer (Python) ──► Ledger (SQLite / DynamoDB)
      │
      ▼
 Reply + card (ledger status / forecast / ballot result)

### MCP Tools

Serion's agent is built around a fixed set of tools, mirroring how a real Alexa+ MCP server would expose functionality:

`log_payment_claim` · `confirm_payment` · `get_status` · `ingest_receipt_text` · `forecast_payout` · `open_ballot` · `cast_ballot` · `explain_rule` · `cycle_report`

## Tech Stack

- **Backend:** Python, Flask
- **Agent framework:** [Strands Agents SDK](https://github.com/strands-agents)
- **AI layer:** Amazon Bedrock — Nova Lite for everyday tool-calling, Claude Opus 5.5 for payout-forecast reasoning
- **Storage:** SQLite (dev) → Amazon DynamoDB
- **Frontend:** Simple chat UI with a member switcher and card rendering

## What's Real vs. Simulated

Real Alexa+ integration is currently limited to brand partners in Preview, so Serion is built as a **simulated Alexa+ experience** — a web app that reproduces the conversational, stateful, card-based interaction model Alexa+ uses, calling Amazon Bedrock directly rather than through a live Alexa+ deployment. The tool-calling architecture mirrors a real MCP server design, so it's a straightforward upgrade path if/when broader access opens up.

## Getting Started

> Setup instructions will be filled in once the initial build lands — see `/app` for progress.

```bash
git clone <repo-url>
cd serion
pip install -r requirements.txt
cp .env.example .env 
python app.py
```

## Project Status

This project is being built for a live hackathon submission (deadline: Oct 23, 2026). Progress and known issues are tracked in [`FRICTION_LOG.md`](./FRICTION_LOG.md).

## Guardrails

- Serion is **record-keeping only** — it never holds or moves real money.
- All demo data is fictional, using a seeded sample group.

## License
MIT

## Acknowledgments

Built by Marvin, a BIT student at Mbarara University of Science and Technology (MUST), Uganda, for the Build, Ship, Shape: Amazon Developer Hackathon.
