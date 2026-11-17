"""
Shared template engine for admin-configurable entity numbering (bought-item order
numbers, made-item numbers, ...). Templates support a small placeholder whitelist,
{year}, {yy}, {month}, and a trailing {seq} / {seq:0Nd}, substituted via regex
rather than str.format(), so admin input can never reach attribute/index traversal
(e.g. "{0.__class__}").

{seq} must be the last token in the template: the rendered prefix then keys
the number counter (adapters/outbound/persistence/number_counters.py), whose
sequence is the trailing digits, and numbering restarts whenever {year} is
included, since last year's numbers no longer share this year's prefix.
"""

import re
from datetime import date

_SEQ_TOKEN_RE = re.compile(r"\{seq(?::0(\d+)d)?\}$")
_DATE_PLACEHOLDER_RE = re.compile(r"\{(year|yy|month)\}")


def validate_numbering_format(template: str) -> None:
    if not template or not template.strip():
        raise ValueError("Numbering format must not be empty.")

    seq_match = _SEQ_TOKEN_RE.search(template)
    if not seq_match:
        raise ValueError("Numbering format must end with a '{seq}' or '{seq:0Nd}' placeholder.")

    body = template[: seq_match.start()]
    remainder = _DATE_PLACEHOLDER_RE.sub("", body)
    if "{" in remainder or "}" in remainder:
        raise ValueError(
            "Numbering format only supports {year}, {yy}, {month} placeholders "
            "before a trailing {seq}."
        )


def render_prefix(template: str, *, today: date) -> tuple[str, int]:
    """Returns (literal prefix with date placeholders substituted, seq zero-pad width)."""
    seq_match = _SEQ_TOKEN_RE.search(template)
    if not seq_match:
        raise ValueError("Numbering format must end with a '{seq}' or '{seq:0Nd}' placeholder.")
    width = int(seq_match.group(1)) if seq_match.group(1) else 1

    values = {
        "year": f"{today.year:04d}",
        "yy": f"{today.year % 100:02d}",
        "month": f"{today.month:02d}",
    }
    prefix = _DATE_PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], template[: seq_match.start()])
    return prefix, width


def render_example(template: str, *, today: date, seq: int = 1) -> str:
    prefix, width = render_prefix(template, today=today)
    return f"{prefix}{str(seq).zfill(width)}"


# ── External (PDM) part-number pattern ───────────────────────────────
#
# Settings-time overlap check (docs/FIELD_OWNERSHIP.md principle 1): an
# admin-configured external pattern reserves a number space for PDM
# ingest, so saving it is rejected if it would also match a number this
# same settings domain's own internal format could generate; such a
# hand-typed number would be ambiguous about which system it belongs to.


def validate_external_pattern(pattern: str) -> None:
    """Compiles `pattern`, raising ValueError with re's message on a bad
    regex. An empty string is valid and means "no external pattern
    configured", the default state when external numbering is off."""
    if not pattern:
        return
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid external part-number pattern {pattern!r}: {exc}") from exc


def assert_pattern_does_not_shadow_internal_formats(
    pattern: str, internal_formats: list[str], *, today: date
) -> None:
    """No-op for an empty pattern. Otherwise renders each of
    `internal_formats`' example (seq=1) and rejects the pattern if it
    fully matches any of them."""
    if not pattern:
        return
    compiled = re.compile(pattern)
    for template in internal_formats:
        example = render_example(template, today=today)
        if compiled.fullmatch(example):
            raise ValueError(
                f"External part-number pattern {pattern!r} matches the internal "
                f"format {template!r}'s rendered example {example!r}; choose a "
                "pattern that cannot collide with internally generated numbers."
            )
