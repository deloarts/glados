"""
Unit test for main.py's `_open_outbox` (inside _make_outbox_relay): it must
call release_lock() on the SqlAlchemyEventOutbox it yields every time,
whether the `async with` body returns normally or raises. That call is what
actually ends the dedicated connection's transaction and releases the PG
advisory lock (see SqlAlchemyEventOutbox's docstring and
advisory_lock.py). Only `_make_outbox_relay` and the two names it wires up
are imported/monkeypatched, same "no running app, no DB, no Redis" style
as test_background_task_supervision.py.
"""

import pytest

import src.bootstrap.main as main_module


class FakeOutbox:
    def __init__(self) -> None:
        self.released = False

    async def release_lock(self) -> None:
        self.released = True


class FakeSessionCtx:
    """Stands in for `async with SessionLocal() as db:`; it yields a sentinel,
    SqlAlchemyEventOutbox is monkeypatched below so the sentinel is never
    actually used as a real AsyncSession."""

    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


def _patch(monkeypatch, outbox: FakeOutbox) -> None:
    monkeypatch.setattr(main_module, "SessionLocal", lambda: FakeSessionCtx())
    monkeypatch.setattr(main_module, "SqlAlchemyEventOutbox", lambda db: outbox)


async def test_release_lock_is_called_after_a_normal_exit(monkeypatch):
    outbox = FakeOutbox()
    _patch(monkeypatch, outbox)

    relay = main_module._make_outbox_relay()
    async with relay._open_outbox() as yielded:
        assert yielded is outbox
        assert outbox.released is False  # not yet, still inside the block

    assert outbox.released is True


async def test_release_lock_is_called_even_when_the_body_raises(monkeypatch):
    outbox = FakeOutbox()
    _patch(monkeypatch, outbox)

    relay = main_module._make_outbox_relay()
    with pytest.raises(RuntimeError, match="boom"):
        async with relay._open_outbox():
            raise RuntimeError("boom")

    assert outbox.released is True
