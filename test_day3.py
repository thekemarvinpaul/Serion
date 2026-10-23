"""
Day 3 checkpoint for Serion.

Goal: prove forecast_payout correctly weighs the FULL roster (not just
people who've bothered to claim a payment), and that the receipt
parser pulls sensible fields out of realistic pasted text.

Run with: python test_day3.py
"""

from ledger.db import init_db
from ledger.models import (
    add_member, add_cycle, add_member_to_cycle,
    log_payment_claim, confirm_payment, forecast_payout,
)
from ledger.parsing import ingest_receipt_text

print("Setting up a fresh demo database...\n")
init_db()

# A 3-person circle: Ben and Grace pay into Ana this round
add_member("Ben")
add_member("Grace")
add_member("Ana")
cycle_id = add_cycle("October Circle", contribution_amount=50)

for name in ("Ben", "Grace", "Ana"):
    add_member_to_cycle(cycle_id, name)

print("1. Forecast BEFORE anyone pays (should show 0% and both names)...")
print("  ", forecast_payout(cycle_id, receiver_name="Ana")["message"], "\n")

# Ben pays and Grace confirms it isn't needed here — Ben pays Ana directly
claim = log_payment_claim(cycle_id, payer_name="Ben", receiver_name="Ana", amount=50)
confirm_payment(claim["claim_id"], confirming_member_name="Ana")

print("2. Forecast after ONLY Ben has paid and been confirmed...")
result = forecast_payout(cycle_id, receiver_name="Ana")
print("  ", result["message"])
print("   (outstanding:", result["outstanding_members"], ")\n")

# Grace pays too
claim2 = log_payment_claim(cycle_id, payer_name="Grace", receiver_name="Ana", amount=50)
confirm_payment(claim2["claim_id"], confirming_member_name="Ana")

print("3. Forecast after EVERYONE has paid and confirmed...")
result = forecast_payout(cycle_id, receiver_name="Ana")
print("  ", result["message"], "\n")

print("4. Testing the receipt text parser on realistic messages:\n")
samples = [
    "You have received UGX 50,000 from GRACE NAKATO. Your new balance is UGX 120,000.",
    "Received $50 from Ben.",
    "John sent you 30,000 UGX",
    "Confirmed: KES 1,200 deposit",  # deliberately no sender name
]
for s in samples:
    parsed = ingest_receipt_text(s)
    print(f"   \"{s}\"")
    print(f"   -> amount={parsed['parsed_amount']}, sender={parsed['parsed_sender']}, "
          f"confidence={parsed['confidence']}\n")
