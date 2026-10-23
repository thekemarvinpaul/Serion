"""
Day 2 checkpoint for Serion.

Goal: prove the core trust mechanism works, with zero AI involved.
A payment claim should stay 'pending' until the actual RECEIVER
confirms it — and nobody else should be able to confirm it for them.

Run with: python test_ledger.py
"""

from ledger.db import init_db
from ledger.models import add_member, add_cycle, log_payment_claim, confirm_payment, get_status

print("Setting up a fresh demo database...\n")
init_db()

# Set up a tiny demo circle
ben_id = add_member("Ben")
grace_id = add_member("Grace")
cycle_id = add_cycle("October Circle", contribution_amount=50)

# Ben claims he paid Grace
print("1. Ben claims he paid Grace 50...")
claim = log_payment_claim(cycle_id, payer_name="Ben", receiver_name="Grace", amount=50)
print(f"   -> {claim['message']}\n")
claim_id = claim["claim_id"]

# Ben tries to confirm his OWN claim — this should fail
print("2. Ben tries to confirm his own payment (should be rejected)...")
result = confirm_payment(claim_id, confirming_member_name="Ben")
print(f"   -> {result}\n")

# Grace confirms it properly — this should succeed
print("3. Grace confirms she received it (should succeed)...")
result = confirm_payment(claim_id, confirming_member_name="Grace")
print(f"   -> {result['message']}\n")

# Check the status of the whole cycle
print("4. Full cycle status:")
status = get_status(cycle_id)
for c in status["claims"]:
    print(f"   {c['payer_name']} -> {c['receiver_name']}: "
          f"{c['amount']} ({c['status']})")
