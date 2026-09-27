# payments/utils.py
import uuid


def generate_receipt_number() -> str:
    """
    Generate a human-friendly receipt number.

    Example: RC-2026-AB12CD

    You can replace this with a sequential number generator later,
    but UUID-based receipts are fine for most internal ERPs.
    """
    raw = uuid.uuid4().hex[:6].upper()
    return f"RC-{raw}"
