"""
Unit test for the advisory-lock guard added around _notification_tick
(main.py): when SqlAlchemyNotificationLock(engine).lock() yields False
(another of gunicorn's four workers already holds this tick),
SendPendingNotifications must never run. Only the module-level helper is
imported/monkeypatched, the same "no running app, no DB, no Redis" style as
test_background_task_supervision.py, which this file sits next to. Every
concrete class _notification_tick constructs is monkeypatched out so the
test never touches a real table (unit tests get no schema, unlike the
integration suite's `_schema` fixture).

Existing SendPendingNotifications tests (test_notification_use_cases.py)
are untouched; this only covers the new tick wrapper around it.
"""

import logging
from contextlib import asynccontextmanager

import src.bootstrap.main as main_module


class FakeLock:
    """Records that it was constructed with an engine and yields a fixed
    lock() verdict, standing in for SqlAlchemyNotificationLock."""

    def __init__(self, engine: object, *, acquired: bool) -> None:
        self.engine = engine
        self.acquired = acquired

    @asynccontextmanager
    async def lock(self):
        yield self.acquired


class FakeAdminSettingsRepo:
    """Stands in for SqlAlchemyAdminSettingsRepository: no DB access, just
    enough surface for _notification_tick's two call sites (get_mail() for
    the mail service, and the repo itself passed to SendPendingNotifications)."""

    def __init__(self, db: object) -> None:
        self.db = db

    async def get_mail(self) -> None:
        return None


def _no_op_ctor(db: object) -> object:
    """Stands in for the repo constructors _notification_tick calls that
    only store `db` and never query it eagerly (SqlAlchemyEmailNotification-
    Repository, SqlAlchemyUserRepository), patched anyway so the test
    never depends on their real constructors staying side-effect-free."""
    return object()


def _patch_common(monkeypatch, *, lock_acquired: bool) -> None:
    monkeypatch.setattr(
        main_module,
        "SqlAlchemyNotificationLock",
        lambda engine: FakeLock(engine, acquired=lock_acquired),
    )
    monkeypatch.setattr(main_module, "SqlAlchemyAdminSettingsRepository", FakeAdminSettingsRepo)
    monkeypatch.setattr(main_module, "SqlAlchemyEmailNotificationRepository", _no_op_ctor)
    monkeypatch.setattr(main_module, "SqlAlchemyUserRepository", _no_op_ctor)
    monkeypatch.setattr(
        main_module, "SmtpMailService", lambda mail_settings, settings_repo=None: None
    )


def _not_called(*args: object, **kwargs: object) -> None:
    raise AssertionError("SendPendingNotifications must not run when the tick lock is not held")


async def test_tick_skips_send_when_lock_not_acquired(monkeypatch, glados_caplog):
    _patch_common(monkeypatch, lock_acquired=False)
    monkeypatch.setattr(main_module, "SendPendingNotifications", _not_called)

    await main_module._notification_tick()  # must return quietly, no AssertionError raised

    debug_records = [r for r in glados_caplog.records if r.levelno == logging.DEBUG]
    assert any("skip" in r.getMessage().lower() for r in debug_records)


async def test_tick_runs_send_when_lock_is_acquired(monkeypatch):
    calls: list[str] = []

    class FakeSendPendingNotifications:
        def __init__(self, **kwargs: object) -> None:
            calls.append("constructed")

        async def execute(self) -> int:
            calls.append("executed")
            return 0

    _patch_common(monkeypatch, lock_acquired=True)
    monkeypatch.setattr(main_module, "SendPendingNotifications", FakeSendPendingNotifications)

    await main_module._notification_tick()

    assert calls == ["constructed", "executed"]


async def test_tick_swallows_exceptions_and_logs(monkeypatch, glados_caplog):
    def _boom(engine: object) -> FakeLock:
        raise RuntimeError("DB is down")

    monkeypatch.setattr(main_module, "SqlAlchemyNotificationLock", _boom)

    await main_module._notification_tick()  # must not raise

    assert [r for r in glados_caplog.records if r.levelno == logging.ERROR]


async def test_tick_failure_sends_a_schedule_error_alert(monkeypatch):
    """_notification_tick's except block builds a fresh NotifyScheduleError
    and calls it with task_name="notifications"
    and the exception's own message."""

    def _boom(engine: object) -> FakeLock:
        raise RuntimeError("DB is down")

    monkeypatch.setattr(main_module, "SqlAlchemyNotificationLock", _boom)
    monkeypatch.setattr(main_module, "SqlAlchemyAdminSettingsRepository", FakeAdminSettingsRepo)
    monkeypatch.setattr(
        main_module, "SmtpMailService", lambda mail_settings, settings_repo=None: None
    )
    monkeypatch.setattr(main_module, "RedisReplayGuard", lambda client: None)
    monkeypatch.setattr(main_module, "get_async_redis_client", lambda: None)

    calls: list[object] = []

    class FakeNotifier:
        def __init__(self, mail_service: object, replay_guard: object) -> None:
            calls.append("constructed")

        async def execute(self, task_name: str, message: str) -> None:
            calls.append((task_name, message))

    monkeypatch.setattr(main_module, "NotifyScheduleError", FakeNotifier)

    await main_module._notification_tick()

    assert calls == ["constructed", ("notifications", "DB is down")]


async def test_tick_failure_alert_itself_never_raises(monkeypatch, glados_caplog):
    """Guard the guard: even if building the alert's own dependencies
    fails, _notification_tick's except block must not propagate."""

    def _boom(engine: object) -> FakeLock:
        raise RuntimeError("DB is down")

    monkeypatch.setattr(main_module, "SqlAlchemyNotificationLock", _boom)

    def _also_broken(db: object) -> object:
        raise RuntimeError("DB really is down")

    monkeypatch.setattr(main_module, "SqlAlchemyAdminSettingsRepository", _also_broken)

    await main_module._notification_tick()  # must not raise

    errors = [r for r in glados_caplog.records if r.levelno == logging.ERROR]
    assert any("tick-failure alert" in r.getMessage() for r in errors)
