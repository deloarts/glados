"""
Unit tests for NotifyScheduleError: claims the cooldown key before sending,
never raises regardless of what the replay guard or mail service do.
"""

from src.modules.platform.application.use_cases.system.notify_schedule_error import (
    NotifyScheduleError,
)


class FakeMailService:
    def __init__(self, raises: Exception | None = None) -> None:
        self.raises = raises
        self.sent: list[tuple[str, str]] = []

    async def send_schedule_error(self, task_name: str, message: str) -> None:
        if self.raises is not None:
            raise self.raises
        self.sent.append((task_name, message))


class FakeReplayGuard:
    def __init__(self, *, claims: bool = True, raises: Exception | None = None) -> None:
        self.claims = claims
        self.raises = raises
        self.calls: list[tuple[str, int]] = []

    async def consume_once(self, key: str, ttl_seconds: int) -> bool:
        self.calls.append((key, ttl_seconds))
        if self.raises is not None:
            raise self.raises
        return self.claims


class TestNotifyScheduleError:
    async def test_claims_the_task_specific_cooldown_key_before_sending(self):
        guard = FakeReplayGuard()
        mail = FakeMailService()

        await NotifyScheduleError(mail, guard).execute("backup", "disk full")

        assert guard.calls == [("alert:schedule_error:backup", 6 * 60 * 60)]
        assert mail.sent == [("backup", "disk full")]

    async def test_a_second_call_within_the_cooldown_does_not_send(self):
        guard = FakeReplayGuard(claims=False)
        mail = FakeMailService()

        await NotifyScheduleError(mail, guard).execute("backup", "disk full")

        assert mail.sent == []

    async def test_each_task_name_gets_its_own_cooldown_key(self):
        guard = FakeReplayGuard()
        mail = FakeMailService()
        notifier = NotifyScheduleError(mail, guard)

        await notifier.execute("backup", "m1")
        await notifier.execute("notifications", "m2")
        await notifier.execute("backup-scheduler", "m3")

        assert [key for key, _ in guard.calls] == [
            "alert:schedule_error:backup",
            "alert:schedule_error:notifications",
            "alert:schedule_error:backup-scheduler",
        ]
        assert len(mail.sent) == 3

    async def test_a_replay_guard_error_is_swallowed_no_send_no_raise(self):
        guard = FakeReplayGuard(raises=RuntimeError("redis down"))
        mail = FakeMailService()

        await NotifyScheduleError(mail, guard).execute("backup", "disk full")  # must not raise

        assert mail.sent == []

    async def test_a_mail_failure_is_swallowed(self):
        guard = FakeReplayGuard()
        mail = FakeMailService(raises=RuntimeError("smtp exploded"))

        await NotifyScheduleError(mail, guard).execute("backup", "disk full")  # must not raise

        # The cooldown was claimed once before the send that failed.
        assert len(guard.calls) == 1
