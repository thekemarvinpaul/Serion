

import re

AMOUNT_PATTERN = re.compile(
    r"(?:UGX|USD|\$)?\s?([\d,]+(?:\.\d{1,2})?)\s?(?:UGX|USD)?", re.IGNORECASE
)
FROM_PATTERN = re.compile(r"from\s+([A-Za-z][A-Za-z\s]+?)(?:[.,]|$)", re.IGNORECASE)
SENT_PATTERN = re.compile(r"^([A-Za-z][A-Za-z\s]+?)\s+sent\s+you", re.IGNORECASE)


def ingest_receipt_text(text: str) -> dict:
    """
    Pulls an amount and a sender name out of pasted receipt text.
    Returns what it found — doesn't guess what it can't find.
    """
    text = text.strip()

    amount = None
    amount_match = AMOUNT_PATTERN.search(text)
    if amount_match:
        amount = float(amount_match.group(1).replace(",", ""))

    sender = None
    from_match = FROM_PATTERN.search(text)
    sent_match = SENT_PATTERN.search(text)
    if from_match:
        sender = from_match.group(1).strip().title()
    elif sent_match:
        sender = sent_match.group(1).strip().title()

    return {
        "raw_text": text,
        "parsed_amount": amount,
        "parsed_sender": sender,
        "confidence": "low" if not (amount and sender) else "medium",
    }


if __name__ == "__main__":
    samples = [
        "You have received UGX 50,000 from GRACE NAKATO. Your new balance is UGX 120,000.",
        "Received $50 from Ben.",
        "John sent you 30,000 UGX",
        "Confirmed: KES 1,200 deposit",  # no sender — tests the "doesn't guess" behavior
    ]
    for s in samples:
        print(s)
        print(" ->", ingest_receipt_text(s))
        print()
