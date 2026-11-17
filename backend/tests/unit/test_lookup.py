"""
Unit tests for found_or_raise (src/modules/platform/application/services/lookup.py), which
turns an optional repository read into the entity or a not-found error with
the caller's own message.
"""

from dataclasses import dataclass

import pytest

from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.platform.application.services.lookup import found_or_raise


@dataclass
class _Row:
    id: int


class TestFoundOrRaise:
    def test_found_or_raise_returns_the_entity_itself(self):
        row = _Row(id=7)
        assert found_or_raise(row, LotNotFoundError, "Lot #7 not found.") is row

    def test_found_or_raise_raises_the_given_error_with_the_message(self):
        with pytest.raises(LotNotFoundError) as exc:
            found_or_raise(None, LotNotFoundError, "Lot #7 not found.")
        assert str(exc.value) == "Lot #7 not found."

    def test_found_or_raise_returns_a_falsy_value_that_is_not_none(self):
        assert found_or_raise(0, LotNotFoundError, "unused") == 0

    def test_found_or_raise_accepts_an_error_factory(self):
        with pytest.raises(LotNotFoundError, match=r"^built: x$"):
            found_or_raise(None, lambda message: LotNotFoundError(f"built: {message}"), "x")
