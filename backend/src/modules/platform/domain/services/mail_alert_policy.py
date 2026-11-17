"""
Validation for AdminMailSettings.alert_recipients, the ops-alert mailing
list that the schedule error and disk space warning mails are sent to.
"""


def normalise_alert_recipients(entries: list[str]) -> list[str]:
    """Strips whitespace, drops empty entries and duplicates (order kept), and
    rejects anything without an @ with text on both sides.

    Raises ValueError naming the first bad entry, which the calling Pydantic
    field_validator turns into a 422. A full RFC 5322 check is not worth it for
    an internal alert list, where a typo is all this needs to catch.
    """
    seen: set[str] = set()
    result: list[str] = []
    for raw in entries:
        entry = raw.strip()
        if not entry:
            continue
        if entry in seen:
            continue
        local, _, domain = entry.partition("@")
        if not local or not domain or "@" in domain:
            raise ValueError(f"{raw!r} is not a valid email address.")
        seen.add(entry)
        result.append(entry)
    return result
