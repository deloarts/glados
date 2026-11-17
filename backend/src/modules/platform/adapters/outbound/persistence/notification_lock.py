"""
Advisory lock guarding one tick of the notification-digest loop (main.py's
_notification_task): all four gunicorn workers start their own loop at
process boot, so their 5-minute ticks land on (nearly) the same wall-clock
cadence and would otherwise all drain and email the same queue in the same
window (SendPendingNotifications has no row locking of its own).

See advisory_lock.py's pg_try_advisory_xact_lock for why a dedicated
connection (not the session SendPendingNotifications runs on) is required
to avoid leaking through the app's connection pool instead of releasing
when the tick ends.
"""

from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncEngine

from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.adapters.outbound.persistence.advisory_lock import advisory_lock


class SqlAlchemyNotificationLock:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def lock(self) -> AbstractAsyncContextManager[bool]:
        return advisory_lock(self._engine, AdvisoryLockKey.NOTIFICATION_TICK)
