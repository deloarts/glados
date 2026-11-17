"""
MeetingScheduler: the background jobs of meetings, interval jobs on the
event loop (src/modules/platform/infrastructure/interval_task.py) like the
backup and PDM schedulers.

meeting_notification_flush runs every minute and publishes the bundled
mentions and todo assignments whose five minutes are up; the notification
event worker turns them into notifications and digest entries.
meeting_maintenance runs every hour: it purges meetings past the retention
period, which is off by default, deletes the drafts of meeting notes nobody
applied within 30 days, and once a night, in the tenant's 03:00 hour,
sweeps the stored meeting files no row names any more. Each job takes
an advisory lock of its own, so one worker acts per tick; the sweep and the
purge change nothing when they run a second time.
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.repositories.catalogue_settings_repository import (
    SqlAlchemyCatalogueSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.contact_repository import (
    SqlAlchemyContactRepository,
)
from src.modules.platform.adapters.outbound.external.storage.factory import create_storage_adapter
from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.adapters.outbound.persistence.advisory_lock import advisory_lock
from src.modules.platform.adapters.outbound.persistence.event_outbox import OutboxEventBus
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    SqlAlchemyPlatformSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.adapters.outbound.persistence.session import engine
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.domain.exceptions import StorageMigrationError
from src.modules.platform.infrastructure.interval_task import run_every
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.workspace.adapters.outbound.locale.meeting_activity_phrases import (
    meeting_activity_phrases,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_card_repository import (
    SqlAlchemyMeetingCardRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_file_repository import (
    SqlAlchemyMeetingFileRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_notes_draft_repository import (
    SqlAlchemyMeetingNotesDraftRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_notification_queue import (
    SqlAlchemyMeetingNotificationQueue,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.meeting_repository import (
    SqlAlchemyMeetingRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_repository import (
    SqlAlchemyProductRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.application.use_cases.meeting._support import MeetingPorts
from src.modules.workspace.application.use_cases.meeting.maintenance import (
    FlushMeetingNotifications,
)
from src.modules.workspace.application.use_cases.meeting.maintenance import PurgeExpiredMeetings
from src.modules.workspace.application.use_cases.meeting.maintenance import SweepOrphanMeetingFiles
from src.modules.workspace.application.use_cases.meeting.notes_drafts import (
    PurgeExpiredMeetingNotesDrafts,
)
from src.shared_kernel.domain.services.clock import now_utc

_FLUSH_INTERVAL_SECONDS = 60
_MAINTENANCE_INTERVAL_SECONDS = 60 * 60
# The tenant's wall-clock hour the nightly sweep runs in. An hourly tick
# lands in it once a night.
_SWEEP_HOUR = 3


async def _storage(settings: SqlAlchemyPlatformSettingsRepository) -> IStoragePort | None:
    storage = await settings.get_storage()
    if not storage.enabled:
        return None
    try:
        return create_storage_adapter(storage)
    except StorageMigrationError:
        return None


async def build_meeting_ports(db: AsyncSession) -> MeetingPorts:
    """The meeting ports on a session of a background job."""
    settings = SqlAlchemyCatalogueSettingsRepository(db)
    return MeetingPorts(
        meetings=SqlAlchemyMeetingRepository(db),
        cards=SqlAlchemyMeetingCardRepository(db),
        files=SqlAlchemyMeetingFileRepository(db),
        queue=SqlAlchemyMeetingNotificationQueue(db),
        projects=SqlAlchemyProjectRepository(db),
        products=SqlAlchemyProductRepository(db),
        contacts=SqlAlchemyContactRepository(db),
        settings=settings,
        storage=await _storage(settings),
        uow=SqlAlchemyUnitOfWork(db),
    )


class MeetingScheduler:
    def start(self) -> list[asyncio.Task[None]]:
        """Starts both jobs as background tasks for the lifespan to supervise
        and cancel on shutdown."""
        return [
            asyncio.create_task(
                run_every(_FLUSH_INTERVAL_SECONDS, self.flush_tick, "meeting_notification_flush"),
                name="meeting-notification-flush",
            ),
            asyncio.create_task(
                run_every(
                    _MAINTENANCE_INTERVAL_SECONDS, self.maintenance_tick, "meeting_maintenance"
                ),
                name="meeting-maintenance",
            ),
        ]

    async def flush_tick(self) -> None:
        async with advisory_lock(engine, AdvisoryLockKey.MEETING_NOTIFICATION_FLUSH) as locked:
            if not locked:
                return
            async with SessionLocal() as db:
                ports = await build_meeting_ports(db)
                sent = await FlushMeetingNotifications(
                    ports, OutboxEventBus(db), meeting_activity_phrases()
                ).execute()
        if sent:
            log.info(f"Meeting notifications: published {sent} bundled notification(s).")

    async def maintenance_tick(self) -> None:
        async with advisory_lock(engine, AdvisoryLockKey.MEETING_MAINTENANCE) as locked:
            if not locked:
                return
            async with SessionLocal() as db:
                ports = await build_meeting_ports(db)
                await PurgeExpiredMeetings(ports).execute()
                await PurgeExpiredMeetingNotesDrafts(
                    SqlAlchemyMeetingNotesDraftRepository(db), ports.uow
                ).execute()
                if now_utc().astimezone(await tenant_zone(ports.settings)).hour == _SWEEP_HOUR:
                    await SweepOrphanMeetingFiles(ports).execute()
