"""
Skip messages that record a deliberate scope decision rather than a
problem: the file sits in a workflow state Glados does not sync, it is not
readable for the PDM user yet, its document type is not ingested for the
matched item's kind, or an admin dismissed it. The reconciliation
report leaves such rows out of its stuck and unmatched categories, since
nothing about them needs fixing.
"""

STATE_NOT_WATCHED = "state not watched"
DOCUMENT_STATE_NOT_RELEASED = "state not released for documents"
UNREADABLE = "not readable for the PDM user (private state or missing read permission)"
DISMISSED_PREFIX = "dismissed by "
DOCUMENT_KIND_EXCLUDED_PREFIX = "extension not ingested for "

_DELIBERATE = frozenset({STATE_NOT_WATCHED, DOCUMENT_STATE_NOT_RELEASED, UNREADABLE})


def dismissed_message(username: str) -> str:
    return f"{DISMISSED_PREFIX}{username}"


def document_kind_excluded_message(kind: str) -> str:
    return f"{DOCUMENT_KIND_EXCLUDED_PREFIX}{kind} items"


def is_deliberate_skip(message: str | None) -> bool:
    """Whether a skipped row's message records a scope decision, not a fault."""
    if message is None:
        return False
    return message in _DELIBERATE or message.startswith(
        (DISMISSED_PREFIX, DOCUMENT_KIND_EXCLUDED_PREFIX)
    )
