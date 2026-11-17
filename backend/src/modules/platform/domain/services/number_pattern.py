"""
Admin-configurable *validation* for hand-entered entity numbers (project numbers,
product numbers). This is the mirror image of numbering_format.py: that module
*generates* numbers from a template, this one *rejects* numbers that do not match
a regex. The two never apply to the same field, numbers that the app generates
need no pattern, and numbers a user types are never generated.

An empty pattern means "no enforcement", which is the shipped default, so
nothing is enforced until an admin opts in.

Matching is full-match (`re.fullmatch`): "^P\\d{5}$" and "P\\d{5}" behave
identically, so a forgotten anchor cannot silently accept "XXP12345YY".

The pattern is admin-supplied and runs on every create/update, so a
catastrophic-backtracking regex would be a self-inflicted DoS. Python's `re` has
no evaluation timeout, so the mitigations are (a) only `write:settings` holders
can set one and (b) MAX_PATTERN_LENGTH bounds how elaborate it can get. That is
a deliberate trade-off, not an oversight: a regex sandbox would cost far more
than the risk of an admin locking up their own install.
"""

import re

MAX_PATTERN_LENGTH = 200


def validate_pattern(pattern: str) -> None:
    """Raise ValueError if `pattern` is unusable as a number pattern. "" is valid (= off)."""
    if not pattern:
        return
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise ValueError(
            f"Number pattern must be at most {MAX_PATTERN_LENGTH} characters (got {len(pattern)})."
        )
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Number pattern is not a valid regular expression: {e}") from e


def matches(value: str, pattern: str) -> bool:
    """True if `value` satisfies `pattern`. An empty pattern accepts everything."""
    if not pattern:
        return True
    try:
        return re.fullmatch(pattern, value) is not None
    except re.error:
        # A stored pattern that does not compile bypassed validation, for
        # example through a direct DB edit. Fail open rather than blocking
        # every create/update in the system on a setting the user cannot see
        # from the form they are being rejected by.
        return True
