"""
The supplier order numbers of an order as they are stored: each one trimmed,
blank entries dropped, and a number entered twice kept once in the spelling
first entered, compared without regard to case. The order of entry is kept,
so the list reads like the confirmations it was copied from.
"""

from collections.abc import Iterable


def normalized_supplier_order_numbers(numbers: Iterable[str]) -> list[str]:
    """The numbers trimmed, without blanks and without case-insensitive
    duplicates, in the order they were given."""
    seen: set[str] = set()
    result: list[str] = []
    for number in numbers:
        text = number.strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def shown_supplier_order_numbers(numbers: Iterable[str]) -> str | None:
    """The numbers as one comma-separated text, as the changelog and the
    supplier mails show them; None when there is none."""
    return ", ".join(numbers) or None
