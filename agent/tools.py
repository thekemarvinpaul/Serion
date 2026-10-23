"""
The tools Serion's agent can call. Each one is a thin wrapper over
ledger/models.py — the agent never touches the database directly,
it only ever calls these.

Docstrings matter here: the LLM reads them to decide which tool
fits what the user said, so keep them clear and specific.
"""

from strands import tool
from ledger import models, ballots
from ledger.parsing import ingest_receipt_text as _parse_receipt


@tool
def log_payment(payer_name: str, receiver_name: str, amount: float) -> str:
    """
    Record that someone claims to have paid another member.

    This does NOT confirm the payment — it stays pending until the
    receiver confirms it themselves. Use this when a user says
    something like "I paid Grace 50" or "Ben sent me 20,000".

    Args:
        payer_name: Name of the member who made the payment.
        receiver_name: Name of the member who was paid.
        amount: How much was paid.
    """
    cycle_id = models.get_current_cycle_id()
    result = models.log_payment_claim(cycle_id, payer_name, receiver_name, amount)
    return result.get("message") or result.get("error")


@tool
def confirm_payment(claim_id: int, confirming_member_name: str,
                     confirmed_amount: float = None) -> str:
    """
    Confirm a pending payment claim. Only the person who RECEIVED
    the payment is allowed to confirm it. If they only received PART
    of the claimed amount, pass confirmed_amount for what was
    actually received — Serion tracks the remainder as a new pending
    claim rather than losing it silently. Use this when a user says
    something like "yes, I received that", "confirm claim 3", or
    "I only got 30 of that 50".

    Args:
        claim_id: The id of the payment claim to confirm.
        confirming_member_name: Name of the member confirming receipt.
        confirmed_amount: Optional. How much was actually received,
            if less than the full claimed amount.
    """
    result = models.confirm_payment(claim_id, confirming_member_name, confirmed_amount)
    return result.get("message") or result.get("error")


@tool
def check_status() -> str:
    """
    Show every payment claim in the current cycle and its status
    (pending or confirmed). Use this when a user asks "what's the
    status?" or "who has paid?".
    """
    cycle_id = models.get_current_cycle_id()
    result = models.get_status(cycle_id)
    if not result["claims"]:
        return "No payments logged yet this cycle."
    lines = [
        f"#{c['id']} {c['payer_name']} -> {c['receiver_name']}: "
        f"{c['amount']} ({c['status']})"
        for c in result["claims"]
    ]
    return "\n".join(lines)


@tool
def check_payout_forecast(receiver_name: str) -> str:
    """
    Check whether a member's upcoming payout is covered yet, and who
    still needs to pay. Use this when a user asks something like
    "can we cover Ana's payout?" or "is Grace's payout ready?".

    Args:
        receiver_name: Name of the member due to receive the payout.
    """
    cycle_id = models.get_current_cycle_id()
    result = models.forecast_payout(cycle_id, receiver_name)
    return result.get("message") or result.get("error")


@tool
def open_ballot(question: str) -> str:
    """
    Open a private vote for something the group needs to decide
    together, like a loan request or an exception to the rules. Use
    this when a user says something like "let's vote on Grace's loan
    request" or "open a ballot for an emergency withdrawal".

    Args:
        question: What the group is voting on, in plain language.
    """
    cycle_id = models.get_current_cycle_id()
    result = ballots.open_ballot(cycle_id, question)
    return result["message"]


@tool
def cast_ballot(ballot_id: int, voter_name: str, choice: str) -> str:
    """
    Record a member's private vote on an open ballot. NEVER reveal
    this vote or any running tally back to the user or to anyone
    else — only confirm that the vote was recorded. Use this when a
    user says something like "I vote yes on ballot 1" or "Grace votes
    no".

    Args:
        ballot_id: The id of the ballot being voted on.
        voter_name: Name of the member casting the vote.
        choice: Either "yes" or "no".
    """
    result = ballots.cast_ballot(ballot_id, voter_name, choice)
    return result.get("message") or result.get("error")


@tool
def check_ballot_result(ballot_id: int) -> str:
    """
    Check the aggregate result of a ballot — total yes/no counts and
    whether it has passed, failed, or is still pending. This NEVER
    reveals who voted which way, only totals. Use this when a user
    asks "what's the result of ballot 1?" or "did the loan pass?".

    Args:
        ballot_id: The id of the ballot to check.
    """
    cycle_id = models.get_current_cycle_id()
    result = ballots.get_ballot_result(ballot_id, cycle_id)
    return result.get("message") or result.get("error")


@tool
def explain_rule() -> str:
    """
    Explain this circle's rules — the late payment fine, the loan
    cap, and how many yes votes a ballot needs to pass. Use this
    when a user asks something like "what's the late fine?", "how
    much can I borrow?", or "how many votes do we need to pass a
    ballot?".
    """
    cycle_id = models.get_current_cycle_id()
    rule = models.get_cycle_rule(cycle_id)
    if "error" in rule:
        return rule["error"]
    return (f"This circle's rules: a late fine of {rule['late_fine']}, "
            f"a loan cap of {rule['loan_cap']}, and ballots need at least "
            f"{rule['quorum']} yes votes to pass.")


@tool
def cycle_report() -> str:
    """
    Give a plain-language summary of this cycle so far — how many
    members, total confirmed, total still pending, and how many
    ballots have been held. Use this when a user asks something like
    "how's the cycle going?" or "give me a summary".
    """
    cycle_id = models.get_current_cycle_id()
    result = models.cycle_report(cycle_id)
    return result.get("message") or result.get("error")


@tool
def parse_receipt_text(text: str) -> str:
    """
    Pull a payment amount and sender name out of pasted receipt or
    mobile money notification text. Use this when a user pastes a
    message instead of describing the payment themselves. After
    parsing, confirm the details with the user before logging them
    with log_payment.

    Args:
        text: The raw pasted receipt or notification text.
    """
    parsed = _parse_receipt(text)
    if not parsed["parsed_amount"]:
        return "Couldn't find an amount in that text — can you confirm it?"
    sender = parsed["parsed_sender"] or "an unknown sender"
    return f"Found: {parsed['parsed_amount']} from {sender} (confidence: {parsed['confidence']})"
