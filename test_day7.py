"""
Checkpoint for partial payments, rules-as-data, and cycle_report.

Run with: python test_day7.py
"""

from ledger.db import init_db
from ledger.models import (
    add_member, add_cycle, add_member_to_cycle,
    log_payment_claim, confirm_payment, forecast_payout,
    get_cycle_rule, cycle_report,
)
from ledger.ballots import open_ballot, cast_ballot, get_ballot_result

print("Setting up a fresh demo database...\n")
init_db()

for name in ("Ben", "Grace", "Ana"):
    add_member(name)
cycle_id = add_cycle("October Circle", contribution_amount=50,
                      late_fine=5, loan_cap=200, quorum=2)
for name in ("Ben", "Grace", "Ana"):
    add_member_to_cycle(cycle_id, name)

print("1. Rules as data:")
print("  ", get_cycle_rule(cycle_id), "\n")

print("2. Ben claims paying Ana 50, Ana confirms only 30 of it...")
claim = log_payment_claim(cycle_id, payer_name="Ben", receiver_name="Ana", amount=50)
result = confirm_payment(claim["claim_id"], confirming_member_name="Ana", confirmed_amount=30)
print("  ", result["message"], "\n")

print("3. Forecast should show Ben still outstanding for the remaining 20, "
      "not wrongly marked as fully paid...")
fc = forecast_payout(cycle_id, receiver_name="Ana")
print("  ", fc["message"])
assert "Ben" in fc["outstanding_members"], "BUG: Ben should still be outstanding after a partial payment"
print("   (confirmed: Ben correctly still shows as outstanding)\n")

print("4. Grace pays Ana in full...")
claim2 = log_payment_claim(cycle_id, payer_name="Grace", receiver_name="Ana", amount=50)
confirm_payment(claim2["claim_id"], confirming_member_name="Ana")

print("5. Cycle report:")
print("  ", cycle_report(cycle_id)["message"], "\n")

print("6. Ballot quorum now comes from the rule (set to 2) instead of a hardcoded majority...")
ballot = open_ballot(cycle_id, "Should Grace receive a 100 loan?")
cast_ballot(ballot["ballot_id"], voter_name="Ben", choice="yes")
cast_ballot(ballot["ballot_id"], voter_name="Grace", choice="yes")
res = get_ballot_result(ballot["ballot_id"], cycle_id)
print("  ", res["message"])
assert res["outcome"] == "approved", "BUG: 2 yes votes should meet quorum=2 and approve"
print("   (confirmed: quorum rule correctly drove the outcome)")
