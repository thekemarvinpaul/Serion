"""
Serion's core ledger logic. No AI here — just the trust mechanism.

A payment only becomes real once the RECEIVER confirms it. That's the
whole point of the project: the payer's claim alone is never enough.
"""

from dataclasses import dataclass
from .db import get_connection


@dataclass
class Member:
    id: int
    name: str


@dataclass
class Cycle:
    id: int
    name: str
    contribution_amount: float
    frequency_days: int


@dataclass
class PaymentClaim:
    id: int
    cycle_id: int
    payer_id: int
    receiver_id: int
    amount: float
    status: str
    source: str
    claimed_at: str


# ---------- Members & Cycles (simple setup helpers) ----------

def add_member(name: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT OR IGNORE INTO members (name) VALUES (?)", (name,)
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM members WHERE name = ?", (name,)
    ).fetchone()
    conn.close()
    return row["id"]


def add_cycle(name: str, contribution_amount: float, frequency_days: int = 7,
              late_fine: float = 0, loan_cap: float = 0, quorum: int = 1) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO cycles (name, contribution_amount, frequency_days) VALUES (?, ?, ?)",
        (name, contribution_amount, frequency_days),
    )
    cycle_id = cur.lastrowid
    conn.execute(
        "INSERT INTO rules (cycle_id, late_fine, loan_cap, quorum) VALUES (?, ?, ?, ?)",
        (cycle_id, late_fine, loan_cap, quorum),
    )
    conn.commit()
    conn.close()
    return cycle_id


def get_cycle_rule(cycle_id: int) -> dict:
    """The current rule set for a cycle — late fine, loan cap, quorum."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM rules WHERE cycle_id = ? ORDER BY id DESC LIMIT 1", (cycle_id,)
    ).fetchone()
    conn.close()
    if not row:
        return {"error": "No rules have been set for this cycle yet."}
    return {"late_fine": row["late_fine"], "loan_cap": row["loan_cap"], "quorum": row["quorum"]}


def get_current_cycle_id():
    """
    For the demo, Serion manages one active cycle at a time, so tools
    don't need to ask 'which cycle?' on every call. Returns the most
    recently created cycle.
    """
    conn = get_connection()
    row = conn.execute("SELECT id FROM cycles ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return row["id"] if row else None


def get_member_by_name(name: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM members WHERE name = ?", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_member_to_cycle(cycle_id: int, member_name: str):
    member = get_member_by_name(member_name)
    if not member:
        return {"error": f"Unknown member: {member_name}"}
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO cycle_members (cycle_id, member_id) VALUES (?, ?)",
        (cycle_id, member["id"]),
    )
    conn.commit()
    conn.close()
    return {"message": f"{member_name} added to the cycle."}


def get_cycle_members(cycle_id: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        """SELECT m.id, m.name FROM cycle_members cm
           JOIN members m ON cm.member_id = m.id
           WHERE cm.cycle_id = ?""",
        (cycle_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ---------- The core mechanism ----------

DUPLICATE_WINDOW_SECONDS = 30


def log_payment_claim(cycle_id: int, payer_name: str, receiver_name: str,
                       amount: float, source: str = "voice") -> dict:
    """
    A member claims they paid someone. This does NOT make it real —
    status starts as 'pending' until the receiver confirms it.

    Guards against accidental duplicates: if the exact same claim
    (same payer, receiver, amount) was logged in the last 30 seconds,
    this returns that existing claim instead of creating a new one.
    That protects against things like a retried network request
    silently double-logging a real payment.
    """
    payer = get_member_by_name(payer_name)
    receiver = get_member_by_name(receiver_name)
    if not payer or not receiver:
        return {"error": f"Unknown member: {'payer' if not payer else 'receiver'}"}

    conn = get_connection()

    recent_duplicate = conn.execute(
        """SELECT id FROM payment_claims
           WHERE cycle_id = ? AND payer_id = ? AND receiver_id = ? AND amount = ?
             AND claimed_at >= datetime('now', ?)
           ORDER BY id DESC LIMIT 1""",
        (cycle_id, payer["id"], receiver["id"], amount,
         f"-{DUPLICATE_WINDOW_SECONDS} seconds"),
    ).fetchone()
    if recent_duplicate:
        conn.close()
        return {
            "claim_id": recent_duplicate["id"],
            "status": "pending",
            "message": f"{payer_name}'s payment of {amount} to {receiver_name} "
                       f"is already logged (claim #{recent_duplicate['id']}).",
        }

    cur = conn.execute(
        """INSERT INTO payment_claims (cycle_id, payer_id, receiver_id, amount, source)
           VALUES (?, ?, ?, ?, ?)""",
        (cycle_id, payer["id"], receiver["id"], amount, source),
    )
    conn.commit()
    claim_id = cur.lastrowid
    conn.close()

    return {
        "claim_id": claim_id,
        "status": "pending",
        "message": f"{payer_name} claims paying {receiver_name} {amount}. "
                   f"Waiting for {receiver_name} to confirm.",
    }


def confirm_payment(claim_id: int, confirming_member_name: str,
                     confirmed_amount: float = None) -> dict:
    """
    Only the RECEIVER of a claim may confirm it. This is the trust
    mechanism — a payer can't confirm their own claim.

    If confirmed_amount is given and is LESS than the claimed amount,
    this is a partial confirmation: the original claim is marked
    'partial' (kept for audit history, never silently edited), a new
    'confirmed' claim is created for what was actually received, and
    a new 'pending' claim is created for the remainder still owed —
    a tracked promise, not a silent loss.
    """
    conn = get_connection()
    claim = conn.execute(
        "SELECT * FROM payment_claims WHERE id = ?", (claim_id,)
    ).fetchone()

    if not claim:
        conn.close()
        return {"error": f"No claim found with id {claim_id}"}

    confirming_member = get_member_by_name(confirming_member_name)
    if not confirming_member or confirming_member["id"] != claim["receiver_id"]:
        conn.close()
        return {"error": "Only the receiver of this payment can confirm it."}

    if claim["status"] != "pending":
        conn.close()
        return {"message": f"This claim is already {claim['status']}, not pending."}

    claimed_amount = claim["amount"]
    received = confirmed_amount if confirmed_amount is not None else claimed_amount

    if received <= 0:
        conn.close()
        return {"error": "Confirmed amount must be greater than zero."}

    if received >= claimed_amount:
        conn.execute(
            "INSERT INTO confirmations (payment_claim_id, confirmed_by) VALUES (?, ?)",
            (claim_id, confirming_member["id"]),
        )
        conn.execute(
            "UPDATE payment_claims SET status = 'confirmed' WHERE id = ?", (claim_id,)
        )
        conn.commit()
        conn.close()
        return {"claim_id": claim_id, "status": "confirmed",
                "message": f"{confirming_member_name} confirmed receiving "
                           f"{claimed_amount} in full."}

    # Partial: split into a confirmed portion + a pending remainder.
    remainder = round(claimed_amount - received, 2)
    conn.execute("UPDATE payment_claims SET status = 'partial' WHERE id = ?", (claim_id,))

    cur = conn.execute(
        """INSERT INTO payment_claims (cycle_id, payer_id, receiver_id, amount, status, source)
           VALUES (?, ?, ?, ?, 'confirmed', 'partial-confirm')""",
        (claim["cycle_id"], claim["payer_id"], claim["receiver_id"], received),
    )
    confirmed_id = cur.lastrowid
    conn.execute(
        "INSERT INTO confirmations (payment_claim_id, confirmed_by) VALUES (?, ?)",
        (confirmed_id, confirming_member["id"]),
    )
    cur2 = conn.execute(
        """INSERT INTO payment_claims (cycle_id, payer_id, receiver_id, amount, status, source)
           VALUES (?, ?, ?, ?, 'pending', 'partial-remainder')""",
        (claim["cycle_id"], claim["payer_id"], claim["receiver_id"], remainder),
    )
    remainder_id = cur2.lastrowid
    conn.commit()
    conn.close()

    return {
        "original_claim_id": claim_id,
        "confirmed_claim_id": confirmed_id,
        "remainder_claim_id": remainder_id,
        "status": "partial",
        "message": (f"{confirming_member_name} confirmed receiving {received} of "
                    f"{claimed_amount}. Claim #{remainder_id} tracks the remaining "
                    f"{remainder} still owed."),
    }


def forecast_payout(cycle_id: int, receiver_name: str) -> dict:
    """
    Can this cycle cover receiver_name's payout right now?
    Compares confirmed payments against the full roster — not just
    whoever has bothered to make a claim.
    """
    conn = get_connection()
    cycle = conn.execute("SELECT * FROM cycles WHERE id = ?", (cycle_id,)).fetchone()
    if not cycle:
        conn.close()
        return {"error": f"No cycle found with id {cycle_id}"}

    receiver = get_member_by_name(receiver_name)
    if not receiver:
        conn.close()
        return {"error": f"Unknown member: {receiver_name}"}

    roster = get_cycle_members(cycle_id)
    payers = [m for m in roster if m["id"] != receiver["id"]]
    required_total = cycle["contribution_amount"] * len(payers)

    confirmed_rows = conn.execute(
        """SELECT payer_id, amount FROM payment_claims
           WHERE cycle_id = ? AND receiver_id = ? AND status = 'confirmed'""",
        (cycle_id, receiver["id"]),
    ).fetchall()
    conn.close()

    confirmed_by_payer = {}
    for row in confirmed_rows:
        confirmed_by_payer[row["payer_id"]] = confirmed_by_payer.get(row["payer_id"], 0) + row["amount"]
    confirmed_total = sum(confirmed_by_payer.values())
    # A payer who's only partially confirmed still owes the rest, so
    # compare against their full expected share, not just "any row".
    outstanding = [m["name"] for m in payers
                   if confirmed_by_payer.get(m["id"], 0) < cycle["contribution_amount"]]

    probability = round(confirmed_total / required_total, 2) if required_total else 0

    return {
        "cycle": cycle["name"],
        "receiver": receiver_name,
        "required_total": required_total,
        "confirmed_total": confirmed_total,
        "coverage": probability,
        "outstanding_members": outstanding,
        "message": (
            f"{receiver_name}'s payout is {int(probability * 100)}% covered "
            f"({confirmed_total}/{required_total}). "
            + (f"Still waiting on: {', '.join(outstanding)}." if outstanding
               else "Everyone has paid.")
        ),
    }


def cycle_report(cycle_id: int) -> dict:
    """Plain-language summary of this cycle so far."""
    conn = get_connection()
    cycle = conn.execute("SELECT * FROM cycles WHERE id = ?", (cycle_id,)).fetchone()
    if not cycle:
        conn.close()
        return {"error": f"No cycle found with id {cycle_id}"}

    claims = conn.execute(
        "SELECT status, amount FROM payment_claims WHERE cycle_id = ?", (cycle_id,)
    ).fetchall()
    ballots_held = conn.execute(
        "SELECT COUNT(*) AS n FROM ballots WHERE cycle_id = ?", (cycle_id,)
    ).fetchone()["n"]
    conn.close()

    roster_size = len(get_cycle_members(cycle_id))
    confirmed = [c for c in claims if c["status"] == "confirmed"]
    pending = [c for c in claims if c["status"] == "pending"]
    confirmed_total = sum(c["amount"] for c in confirmed)
    pending_total = sum(c["amount"] for c in pending)

    return {
        "cycle": cycle["name"],
        "members": roster_size,
        "confirmed_count": len(confirmed),
        "confirmed_total": confirmed_total,
        "pending_count": len(pending),
        "pending_total": pending_total,
        "ballots_held": ballots_held,
        "message": (
            f"{cycle['name']}: {roster_size} members, {len(confirmed)} payment(s) "
            f"confirmed totaling {confirmed_total}, {len(pending)} still pending "
            f"totaling {pending_total}, {ballots_held} ballot(s) held this cycle."
        ),
    }


def get_status(cycle_id: int) -> dict:
    """Plain summary of every claim in a cycle — who's confirmed, who's pending."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT pc.*, p.name AS payer_name, r.name AS receiver_name
           FROM payment_claims pc
           JOIN members p ON pc.payer_id = p.id
           JOIN members r ON pc.receiver_id = r.id
           WHERE pc.cycle_id = ?
           ORDER BY pc.claimed_at""",
        (cycle_id,),
    ).fetchall()
    conn.close()
    return {"claims": [dict(row) for row in rows]}
