"""
Turns a periodic-task failure (a backup job, the
notification tick, the BackupScheduler tick itself) into a mail via
IMailService.send_schedule_error, deduped so a failing 60s/5min tick does
not turn into a mail storm.

Cooldown: claims `alert:schedule_error:{task_name}` for 6h via
IReplayGuard.consume_once *before* sending, so an SMTP outage during the
send must not leave the key unclaimed and re-fire on the very next tick.
Each distinct `task_name` (e.g. "backup", "notifications",
"backup-scheduler") gets its own independent cooldown window.

Entirely non-fatal: every call site here already sits inside its own
broad except-block (run_claimed_backup.py's failure branch, main.py's
notification tick, system_schedule.py's BackupScheduler tick), so nothing
below may ever raise back into the caller. See the try/except around the
whole body. Note on IReplayGuard's current concrete adapter
(RedisReplayGuard): it fails *open* on a genuine Redis outage (returns
True, the behaviour its TOTP-replay-protection caller needs, see that
class's docstring), so in practice a Redis outage does
not by itself suppress this alert: the try/except below covers any
exception the port call raises, not a silent fail-open return value.
"""

from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.mail_service_port import IMailService
from src.modules.platform.ports.outbound.replay_guard_port import IReplayGuard

_COOLDOWN_TTL_SECONDS = 6 * 60 * 60  # 6h


class NotifyScheduleError:
    def __init__(self, mail_service: IMailService, replay_guard: IReplayGuard) -> None:
        self._mail = mail_service
        self._replay_guard = replay_guard

    async def execute(self, task_name: str, message: str) -> None:
        try:
            claimed = await self._replay_guard.consume_once(
                f"alert:schedule_error:{task_name}", _COOLDOWN_TTL_SECONDS
            )
            if not claimed:
                log.debug(
                    "NotifyScheduleError: %r already alerted within the last 6h, skipping.",
                    task_name,
                )
                return
            # _send_alert (SmtpMailService) already no-ops on empty
            # alert_recipients / disabled mail, and fans out to every
            # configured recipient independently.
            await self._mail.send_schedule_error(task_name, message)
        except Exception:
            log.error("NotifyScheduleError: failed to alert for task %r.", task_name, exc_info=True)
