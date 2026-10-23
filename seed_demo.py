"""
Seeds a fresh demo circle: Ben, Grace, and Ana, each contributing 50
per round. Run this once before talking to the agent interactively.

Run with: python seed_demo.py
"""

from ledger.db import init_db
from ledger.models import add_member, add_cycle, add_member_to_cycle

init_db()

for name in ("Ben", "Grace", "Ana"):
    add_member(name)

cycle_id = add_cycle("October Circle", contribution_amount=50,
                      late_fine=5, loan_cap=200, quorum=2)

for name in ("Ben", "Grace", "Ana"):
    add_member_to_cycle(cycle_id, name)

print(f"Demo circle ready — cycle #{cycle_id}: Ben, Grace, Ana, 50 each.")
