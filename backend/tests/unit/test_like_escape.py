"""
Coverage for escape_like (src/modules/platform/adapters/outbound/persistence/like_escape.py),
the guard against LIKE wildcard-injection in repository search filters.
"""

from src.modules.platform.adapters.outbound.persistence.like_escape import escape_like


def test_percent_is_escaped() -> None:
    assert escape_like("50%") == "50\\%"


def test_underscore_is_escaped() -> None:
    assert escape_like("a_b") == "a\\_b"


def test_backslash_is_escaped_first() -> None:
    # The backslash must be doubled before the metacharacters, or escaping
    # them would produce a stray unescaped backslash.
    assert escape_like("a\\b") == "a\\\\b"


def test_plain_text_is_unchanged() -> None:
    assert escape_like("ACME Manufacturing") == "ACME Manufacturing"


def test_combined() -> None:
    assert escape_like("100%_\\") == "100\\%\\_\\\\"
