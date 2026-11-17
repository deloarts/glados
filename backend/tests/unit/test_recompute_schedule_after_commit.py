"""
Unit tests for recompute_schedule_after_commit
(src/modules/fulfillment/application/services/schedule_recompute_helpers.py), the guard every
write use case runs after its commit. A failed schedule walk must be logged
and swallowed, because the write it follows is already committed.
"""

import logging

from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)


class _FakeRecompute:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls = 0
        self._error = error

    async def execute_all(self) -> None:
        self.calls += 1
        if self._error is not None:
            raise self._error


async def test_recompute_schedule_after_commit_runs_the_walk_once():
    recompute = _FakeRecompute()

    await recompute_schedule_after_commit(recompute, after="doing a thing; it is committed.")

    assert recompute.calls == 1


async def test_recompute_schedule_after_commit_skips_without_a_recompute():
    await recompute_schedule_after_commit(None, after="doing a thing; it is committed.")


async def test_recompute_schedule_after_commit_logs_and_swallows_a_failure(glados_caplog):
    recompute = _FakeRecompute(error=RuntimeError("walk exploded"))

    await recompute_schedule_after_commit(
        recompute, after="canceling order #7; the cancellation itself is committed."
    )

    assert recompute.calls == 1
    errors = [r for r in glados_caplog.records if r.levelno == logging.ERROR]
    assert [r.getMessage() for r in errors] == [
        "Schedule recompute failed after canceling order #7; the cancellation itself is committed."
    ]
    assert errors[0].exc_info is not None
