"""
Private ballots — for loan requests, exceptions, anything the group
shouldn't have to decide out loud in front of each other.

Key design rule: individual votes are stored (so nobody can vote
twice), but NEVER exposed. Every function here returns only
aggregate counts and an outcome — never "who voted what."
"""

from .db import get_connection
from .models import get_member_by_name, get_cycle_members, get_cycle_rule


def open_ballot(cycle_id: int, question: str) -> dict:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO ballots (cycle_id, question) VALUES (?, ?)",
        (cycle_id, question),
    )
    conn.commit()
    ballot_id = cur.lastrowid
    conn.close()
    return {
        "ballot_id": ballot_id,
        "message": f"Ballot #{ballot_id} opened: \"{question}\". "
                   f"Members can now vote privately.",
    }


def cast_ballot(ballot_id: int, voter_name: str, choice: str) -> dict:
    choice = choice.strip().lower()
    if choice not in ("yes", "no"):
        return {"error": "Vote must be 'yes' or 'no'."}

    voter = get_member_by_name(voter_name)
    if not voter:
        return {"error": f"Unknown member: {voter_name}"}

    conn = get_connection()
    ballot = conn.execute("SELECT * FROM ballots WHERE id = ?", (ballot_id,)).fetchone()
    if not ballot:
        conn.close()
        return {"error": f"No ballot found with id {ballot_id}"}
    if ballot["status"] != "open":
        conn.close()
        return {"error": "This ballot is already closed."}

    existing = conn.execute(
        "SELECT id FROM votes WHERE ballot_id = ? AND voter_id = ?",
        (ballot_id, voter["id"]),
    ).fetchone()
    if existing:
        conn.close()
        return {"message": f"{voter_name} has already voted on this ballot."}

    conn.execute(
        "INSERT INTO votes (ballot_id, voter_id, choice) VALUES (?, ?, ?)",
        (ballot_id, voter["id"], choice),
    )
    conn.commit()
    conn.close()
    # Deliberately does not echo back the choice or any tally —
    # confirming receipt only, never revealing results mid-vote.
    return {"message": f"{voter_name}'s vote has been recorded privately."}


def get_ballot_result(ballot_id: int, cycle_id: int) -> dict:
    """
    Aggregate-only result. The number of yes votes needed to pass
    comes from the cycle's own quorum rule (rules-as-data), not a
    hardcoded majority — so a group can set a stricter bar for big
    decisions if they choose to. Falls back to a simple majority of
    the roster if no rule has been set.
    """
    conn = get_connection()
    ballot = conn.execute("SELECT * FROM ballots WHERE id = ?", (ballot_id,)).fetchone()
    if not ballot:
        conn.close()
        return {"error": f"No ballot found with id {ballot_id}"}

    votes = conn.execute(
        "SELECT choice FROM votes WHERE ballot_id = ?", (ballot_id,)
    ).fetchall()
    conn.close()

    roster_size = len(get_cycle_members(cycle_id))
    yes_count = sum(1 for v in votes if v["choice"] == "yes")
    no_count = sum(1 for v in votes if v["choice"] == "no")
    votes_cast = yes_count + no_count

    rule = get_cycle_rule(cycle_id)
    quorum_needed = rule["quorum"] if "quorum" in rule else (roster_size // 2 + 1)

    if yes_count >= quorum_needed:
        outcome = "approved"
    elif votes_cast >= roster_size:
        # everyone's voted and yes didn't reach majority
        outcome = "rejected"
    else:
        outcome = "pending"

    return {
        "ballot_id": ballot_id,
        "question": ballot["question"],
        "yes": yes_count,
        "no": no_count,
        "votes_cast": votes_cast,
        "roster_size": roster_size,
        "outcome": outcome,
        "message": (
            f"Ballot #{ballot_id} (\"{ballot['question']}\"): "
            f"{yes_count} yes, {no_count} no, {votes_cast}/{roster_size} voted. "
            f"Outcome: {outcome}."
        ),
    }
