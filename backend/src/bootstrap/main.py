"""Composition root, the only place concrete classes are wired together.

The lifespan migrates (dev only), seeds the database, attaches the DB log
handler, then starts this worker's background tasks: interval jobs, the
notification digest, the event consumers, live row-sync and the outbox
relay. Jobs that must run once across workers take an advisory lock or a
claim. Stored files are only ever served through authenticated routes.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.routing import Route

from src.bootstrap.adapters.inbound.api.v1.auth.router import router as auth_router
from src.bootstrap.adapters.inbound.api.v1.key.router import router as key_router
from src.bootstrap.adapters.inbound.api.v1.pat.router import router as pat_router
from src.bootstrap.adapters.inbound.api.v1.public.router import router as public_router
from src.bootstrap.adapters.inbound.api.v1.web.router import router as web_router
from src.bootstrap.adapters.outbound.persistence.init_db import InitDatabase
from src.bootstrap.adapters.outbound.persistence.init_db import run_migrations
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.agents import build_agent_app
from src.bootstrap.registrations import register_all
from src.bootstrap.workers.meeting_schedule import MeetingScheduler
from src.bootstrap.workers.pdm_schedule import PdmPollScheduler
from src.bootstrap.workers.pdm_schedule import build_ingest_pdm_file
from src.bootstrap.workers.pdm_schedule import build_pdm_document_sync
from src.bootstrap.workers.pdm_schedule import build_pdm_thumbnails
from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_repository.item import (
    SqlAlchemyBoughtItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.item_picture_repository import (
    SqlAlchemyItemPictureRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_repository import (
    SqlAlchemySourceItemRepository,
)
from src.modules.catalogue.application.services.item_picture_store import ItemPictureStore
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemEdpPictureRequested
from src.modules.external_data.adapters.outbound.external.eplan_data_portal.factory import (
    close_eplan_data_portals,
)
from src.modules.external_data.adapters.outbound.external.eplan_data_portal.factory import (
    create_eplan_data_portal,
)
from src.modules.external_data.adapters.outbound.external.pdm.factory import close_pdm_gateways
from src.modules.external_data.adapters.outbound.external.pdm.factory import create_pdm_gateway
from src.modules.external_data.adapters.outbound.external.stock_service.factory import (
    close_stock_service_clients,
)
from src.modules.external_data.adapters.outbound.persistence.pdm_file_lock import (
    SqlAlchemyPdmFileLock,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_file_snapshot_repository import (
    SqlAlchemyPdmFileSnapshotRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_folder_poll_state_repository import (
    SqlAlchemyPdmFolderPollStateRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_sync_run_repository import (
    SqlAlchemyPdmSyncRunRepository,
)
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.services.pdm_writeback import PdmWriteBack
from src.modules.external_data.application.use_cases.eplan_data_portal.fill_edp_picture import (
    FillBoughtItemEdpPicture,
)
from src.modules.external_data.application.use_cases.pdm.refresh_pdm_file import RefreshPdmFile
from src.modules.external_data.domain.events.pdm_events import PdmFileChangeRequested
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.fulfillment.adapters.inbound.api.deps.production import build_purge_expired_plans
from src.modules.fulfillment.adapters.inbound.api.deps.production import build_record_plan_baseline
from src.modules.fulfillment.adapters.inbound.api.deps.production import build_schedule_walk
from src.modules.fulfillment.adapters.outbound.external.schedules.schedule_tick import TICK_SECONDS
from src.modules.fulfillment.adapters.outbound.external.schedules.schedule_tick import ScheduleTick
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.domain.events.schedule_events import ScheduleRecomputeRequested
from src.modules.operations.adapters.outbound.external.time_tracking_service.factory import (
    close_time_tracking_clients,
)
from src.modules.operations.adapters.outbound.external.weather.service import close_weather_service
from src.modules.platform.adapters.inbound.api.docs import register_surface_docs
from src.modules.platform.adapters.inbound.api.exception_handlers import register_exception_handlers
from src.modules.platform.adapters.inbound.api.http_metrics import instrument
from src.modules.platform.adapters.inbound.api.live.hub import get_live_hub
from src.modules.platform.adapters.inbound.api.middleware.logging_middleware import (
    DatabaseLoggingMiddleware,
)
from src.modules.platform.adapters.inbound.api.middleware.lost_race_retry_middleware import (
    LostRaceRetryMiddleware,
)
from src.modules.platform.adapters.inbound.api.middleware.request_context_middleware import (
    RequestContextMiddleware,
)
from src.modules.platform.adapters.inbound.api.middleware.security_headers_middleware import (
    SecurityHeadersMiddleware,
)
from src.modules.platform.adapters.inbound.api.middleware.unhandled_exception_middleware import (
    UnhandledExceptionMiddleware,
)
from src.modules.platform.adapters.inbound.api.middleware.version_header_middleware import (
    VersionHeaderMiddleware,
)
from src.modules.platform.adapters.inbound.api.readiness import background_task_warnings_report
from src.modules.platform.adapters.inbound.api.readiness import backup_warnings_report
from src.modules.platform.adapters.inbound.api.readiness import readiness_report
from src.modules.platform.adapters.outbound.external.event_bus.redis_stream_event_bus import (
    RedisStreamEventBus,
)
from src.modules.platform.adapters.outbound.external.login_attempts.redis_replay_guard import (
    RedisReplayGuard,
)
from src.modules.platform.adapters.outbound.external.mail.smtp_mail_service import SmtpMailService
from src.modules.platform.adapters.outbound.external.schedules.system_schedule import (
    BackupScheduler,
)
from src.modules.platform.adapters.outbound.external.storage.factory import create_storage_adapter
from src.modules.platform.adapters.outbound.external.webhook.factory import (
    create_webhook_dispatcher,
)
from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.adapters.outbound.persistence.advisory_lock import advisory_lock
from src.modules.platform.adapters.outbound.persistence.change_tracking import (
    register_change_tracking,
)
from src.modules.platform.adapters.outbound.persistence.event_outbox import SqlAlchemyEventOutbox
from src.modules.platform.adapters.outbound.persistence.event_outbox import register_outbox_tripwire
from src.modules.platform.adapters.outbound.persistence.notification_lock import (
    SqlAlchemyNotificationLock,
)
from src.modules.platform.adapters.outbound.persistence.number_counters import tenant_today
from src.modules.platform.adapters.outbound.persistence.repositories.email_notification_repository import (
    SqlAlchemyEmailNotificationRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.log_repository import (
    persist_log_batch,
)
from src.modules.platform.adapters.outbound.persistence.repositories.notification_repository import (
    SqlAlchemyNotificationRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.webhook_repository import (
    SqlAlchemyWebhookDeliveryRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.webhook_repository import (
    SqlAlchemyWebhookSubscriptionRepository,
)
from src.modules.platform.adapters.outbound.persistence.session import LogSessionLocal
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.adapters.outbound.persistence.session import engine
from src.modules.platform.adapters.outbound.persistence.session import log_engine
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.use_cases.mail.send_pending_notifications import (
    SendPendingNotifications,
)
from src.modules.platform.application.use_cases.notification.handle_event_notifications import (
    HandleEventNotifications,
)
from src.modules.platform.application.use_cases.system.notify_schedule_error import (
    NotifyScheduleError,
)
from src.modules.platform.application.use_cases.webhook.dispatch_event_to_webhooks import (
    DispatchEventToWebhooks,
)
from src.modules.platform.const import API_MCP
from src.modules.platform.const import VERSION
from src.modules.platform.const import VERSION_HEADER
from src.modules.platform.domain.entities.log_entry import LogEntry
from src.modules.platform.domain.exceptions import StorageMigrationError
from src.modules.platform.infrastructure.background_tasks import mark_running as mark_task_running
from src.modules.platform.infrastructure.background_tasks import mark_stopped as mark_task_stopped
from src.modules.platform.infrastructure.config.boot_guard import assert_bundled_storage_secret_ok
from src.modules.platform.infrastructure.config.boot_guard import assert_production_credentials_ok
from src.modules.platform.infrastructure.config.boot_guard import assert_production_secrets_ok
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.events.live_subscriber import LiveEventSubscriber
from src.modules.platform.infrastructure.events.outbox_relay import OutboxRelay
from src.modules.platform.infrastructure.events.stream_trimmer import TRIM_INTERVAL_SECONDS
from src.modules.platform.infrastructure.events.stream_trimmer import trim_events_stream
from src.modules.platform.infrastructure.events.worker import EventWorker
from src.modules.platform.infrastructure.interval_task import run_every
from src.modules.platform.infrastructure.logging.db_log_handler import DatabaseLogHandler
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.redis_client import get_async_redis_client
from src.modules.platform.ports.outbound.event_outbox_port import OutboxMessage
from src.modules.platform.ports.outbound.live_signal import LiveSignal
from src.modules.quality.adapters.outbound.external.printer.factory import create_printer_gateway
from src.modules.quality.adapters.outbound.persistence.repositories.print_job_repository import (
    SqlAlchemyPrintJobRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.print_template_repository import (
    SqlAlchemyPrintTemplateRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.printer_repository import (
    SqlAlchemyPrinterRepository,
)
from src.modules.quality.adapters.outbound.rendering.docket_renderer import DocketRenderer
from src.modules.quality.application.services.docket_asset_resolver import DocketAssetResolver
from src.modules.quality.application.use_cases.print_document.handle_event_auto_print import (
    HandleEventAutoPrint,
)
from src.modules.quality.application.use_cases.print_document.print_document import PrintDocument
from src.read.adapters.inbound.api.metrics import metrics_response
from src.read.application.services.print_root_resolver import PrintRootResolver
from src.shared_kernel.domain.events.base import DomainEvent

_NOTIFICATION_INTERVAL_SECONDS = 300  # 5 minutes
# The plan baseline job looks every 15 minutes whether the day still needs
# its baseline, so it is recorded soon after the night walk.
PLAN_BASELINE_TICK_SECONDS = 15 * 60


def _log_task_completion(task: asyncio.Task[Any]) -> None:
    """Reports a background task that ended, which would otherwise die
    silently: a CRITICAL log record, with the traceback when it crashed, and
    the task's `glados_background_task_up` gauge at 0, which `/ready` lists
    as a warning. No restart: the long-running loops supervise themselves,
    so a task that still ends signals something a respawn would only loop
    on. Cancellation is the normal shutdown and reports nothing. The body
    never raises into the event loop.
    """
    try:
        if task.cancelled():
            return  # normal shutdown path
        name = task.get_name()
        mark_task_stopped(name)
        exc = task.exception()
        if exc is not None:
            log.critical("Background task %r died: %s", name, exc, exc_info=exc)
        else:
            log.critical("Background task %r ended although it should run forever.", name)
    except Exception:
        pass


async def _notification_task() -> None:
    """Background loop: drain the email notification queue every 5 minutes."""
    while True:
        await asyncio.sleep(_NOTIFICATION_INTERVAL_SECONDS)
        await _notification_tick()


async def _notification_tick() -> None:
    """One notification pass under an advisory lock, because every worker
    ticks at nearly the same time and sending has no row locking. The lock
    lives on its own connection and is released after the deletes commit.
    """
    try:
        async with SqlAlchemyNotificationLock(engine).lock() as locked:
            if not locked:
                log.debug("Notification task: another worker holds the tick lock, skipping.")
                return
            async with SessionLocal() as db:
                settings_repo = SqlAlchemyAdminSettingsRepository(db)
                mail_service = SmtpMailService(
                    await settings_repo.get_mail(), settings_repo=settings_repo
                )
                sent = await SendPendingNotifications(
                    notification_repo=SqlAlchemyEmailNotificationRepository(db),
                    user_repo=SqlAlchemyUserRepository(db),
                    mail_service=mail_service,
                    admin_settings_repo=settings_repo,
                    uow=SqlAlchemyUnitOfWork(db),
                ).execute()
        if sent:
            log.info("Notification task: sent %d digest email(s).", sent)
    except Exception as exc:
        log.exception("Notification task failed; will retry next interval.")
        await _notify_notification_tick_failure(str(exc))


async def _notify_notification_tick_failure(message: str) -> None:
    """Best-effort alert for a crashed tick, on its own session, never
    raising."""
    try:
        async with SessionLocal() as db:
            settings_repo = SqlAlchemyAdminSettingsRepository(db)
            await NotifyScheduleError(
                mail_service=SmtpMailService(
                    await settings_repo.get_mail(), settings_repo=settings_repo
                ),
                replay_guard=RedisReplayGuard(get_async_redis_client()),
            ).execute("notifications", message)
    except Exception:
        log.exception("Notification task: failed to send tick-failure alert.")


async def _handle_notification_event(event: DomainEvent, message_id: str) -> None:
    """Event bus handler ("notifications" group): create in-app
    notifications, and send an immediate system mail for the four event
    kinds that warrant one."""
    async with SessionLocal() as db:
        settings_repo = SqlAlchemyAdminSettingsRepository(db)
        await HandleEventNotifications(
            inapp_notification_repo=SqlAlchemyNotificationRepository(db),
            email_notification_repo=SqlAlchemyEmailNotificationRepository(db),
            user_repo=SqlAlchemyUserRepository(db),
            mail_service=SmtpMailService(
                await settings_repo.get_mail(), settings_repo=settings_repo
            ),
            admin_settings_repo=settings_repo,
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(event, message_id)


async def _handle_webhook_event(event: DomainEvent, message_id: str) -> None:
    """Event bus handler ("webhooks" group): deliver the event to subscribers."""
    async with SessionLocal() as db:
        await DispatchEventToWebhooks(
            subscription_repo=SqlAlchemyWebhookSubscriptionRepository(db),
            delivery_repo=SqlAlchemyWebhookDeliveryRepository(db),
            dispatcher=create_webhook_dispatcher(),
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(event, message_id)


async def _handle_auto_print_event(event: DomainEvent, message_id: str) -> None:
    """Event bus handler ("auto_print" group). Kept off the request, so a
    broken printer never fails or slows a shop-floor completion."""
    async with SessionLocal() as db:
        admin_settings_repo = SqlAlchemyAdminSettingsRepository(db)
        template_repo = SqlAlchemyPrintTemplateRepository(db)
        job_repo = SqlAlchemyPrintJobRepository(db)
        root_resolver = PrintRootResolver(
            order_repo=SqlAlchemyOrderRepository(db),
            order_item_repo=SqlAlchemyOrderItemRepository(db),
            production_order_repo=SqlAlchemyProductionOrderRepository(db),
            production_lot_repo=SqlAlchemyProductionLotRepository(db),
            made_item_repo=SqlAlchemyMadeItemRepository(db),
            bought_item_repo=SqlAlchemyBoughtItemRepository(db),
            source_item_repo=SqlAlchemySourceItemRepository(db),
            settings_repo=admin_settings_repo,
        )

        storage = None
        storage_settings = await admin_settings_repo.get_storage()
        if storage_settings.enabled:
            try:
                storage = create_storage_adapter(storage_settings)
            except StorageMigrationError:
                storage = None  # a docket still prints, just without its images

        await HandleEventAutoPrint(
            template_repo=template_repo,
            job_repo=job_repo,
            user_repo=SqlAlchemyUserRepository(db),
            root_resolver=root_resolver,
            print_document=PrintDocument(
                template_repo=template_repo,
                printer_repo=SqlAlchemyPrinterRepository(db),
                job_repo=job_repo,
                root_resolver=root_resolver,
                gateway=create_printer_gateway(),
                docket_renderer=DocketRenderer(),
                asset_resolver=DocketAssetResolver(
                    item_picture_repo=SqlAlchemyItemPictureRepository(db),
                    admin_settings_repo=admin_settings_repo,
                    storage=storage,
                ),
                domain_url=cfg.domain,
                uow=SqlAlchemyUnitOfWork(db),
            ),
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(event, message_id)


async def _handle_edp_picture_event(event: DomainEvent, message_id: str) -> None:
    """Event bus handler ("edp_pictures" group): brings a bought item's Data
    Portal picture in line with its portal link. Kept off the request,
    since the portal and the image processing are slow; other event types
    on the shared stream are ignored."""
    if not isinstance(event, BoughtItemEdpPictureRequested):
        return
    async with SessionLocal() as db:
        admin_settings_repo = SqlAlchemyAdminSettingsRepository(db)
        picture_repo = SqlAlchemyItemPictureRepository(db)
        store = None
        storage_settings = await admin_settings_repo.get_storage()
        if storage_settings.enabled:
            try:
                store = ItemPictureStore(picture_repo, create_storage_adapter(storage_settings))
            except StorageMigrationError:
                store = None
        await FillBoughtItemEdpPicture(
            item_repo=SqlAlchemyBoughtItemRepository(db),
            picture_repo=picture_repo,
            settings_repo=admin_settings_repo,
            user_repo=SqlAlchemyUserRepository(db),
            portal_factory=create_eplan_data_portal,
            store=store,
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(event)


async def _handle_schedule_event(event: DomainEvent, message_id: str) -> None:
    """Event bus handler ("schedule" group): walks the schedule a write
    requested on a fresh session, unless a walk already covered the
    request's generation. Other event types on the shared stream are
    ignored."""
    if not isinstance(event, ScheduleRecomputeRequested):
        return
    async with SessionLocal() as db:
        await build_schedule_walk(db).walk_covering(event.generation)


async def _walk_schedule() -> None:
    """The periodic tick's walk, coalesced with every other worker's."""
    async with SessionLocal() as db:
        await build_schedule_walk(db).execute_all()


async def _record_plan_baseline() -> None:
    """The plan baseline job: one worker records the day's baseline once and
    purges the expired plans; the others find the lock held and skip. A
    failure is logged and the next run tries again."""
    try:
        async with advisory_lock(engine, AdvisoryLockKey.PLAN_BASELINE) as locked:
            if not locked:
                return
            async with SessionLocal() as db:
                await build_record_plan_baseline(db).execute()
                await build_purge_expired_plans(db).execute()
    except Exception:
        log.exception("Plan baseline job failed.")


async def _tenant_today() -> date:
    async with SessionLocal() as db:
        return await tenant_today(db)


async def _handle_pdm_sync_event(event: DomainEvent, message_id: str) -> None:
    """Event bus handler ("pdm_sync" group): refreshes one PDM file after a
    trigger or an admin retry, recording the run under the matching
    trigger. Other event types on the shared stream are ignored."""
    if not isinstance(event, PdmFileChangeRequested):
        return
    async with SessionLocal() as db:
        admin_settings_repo = SqlAlchemyAdminSettingsRepository(db)
        snapshot_repo = SqlAlchemyPdmFileSnapshotRepository(db)
        made_item_repo = SqlAlchemyMadeItemRepository(db)
        bought_item_repo = SqlAlchemyBoughtItemRepository(db)
        session = PdmSessionService(
            repo=admin_settings_repo,
            gateway_factory=create_pdm_gateway,
            uow=SqlAlchemyUnitOfWork(db),
        )
        run_repo = SqlAlchemyPdmSyncRunRepository(db)
        write_back = PdmWriteBack(
            session=session,
            settings_repo=admin_settings_repo,
            made_repo=made_item_repo,
            bought_repo=bought_item_repo,
            run_repo=run_repo,
        )
        await RefreshPdmFile(
            session=session,
            admin_settings_repo=admin_settings_repo,
            snapshot_repo=snapshot_repo,
            made_item_repo=made_item_repo,
            bought_item_repo=bought_item_repo,
            ingest=build_ingest_pdm_file(db, session),
            write_back=write_back,
            document_sync=await build_pdm_document_sync(db, session),
            thumbnails=await build_pdm_thumbnails(db, session, run_repo),
            run_repo=run_repo,
            folder_poll_state_repo=SqlAlchemyPdmFolderPollStateRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
            file_lock=SqlAlchemyPdmFileLock(engine),
        ).execute(
            vault_name=event.vault_name,
            file_id=event.file_id,
            path=event.path,
            trigger=PdmSyncTrigger.RETRY
            if event.source == "retry"
            else PdmSyncTrigger.FILE_TRIGGER,
            change_reason=event.reason,
            change_state=event.state,
            requested_by_name=event.requested_by_name,
        )


def _make_outbox_relay() -> OutboxRelay:
    """Wires the outbox relay. Redis connects lazily, so a missing Redis
    never breaks startup; events accumulate and drain once it returns."""
    transport = RedisStreamEventBus(get_async_redis_client())

    @asynccontextmanager
    async def open_outbox() -> AsyncIterator[SqlAlchemyEventOutbox]:
        async with SessionLocal() as db:
            outbox = SqlAlchemyEventOutbox(db)
            try:
                yield outbox
            finally:
                # Releases the lock's own connection every tick; idempotent.
                await outbox.release_lock()

    async def publish(message: OutboxMessage) -> None:
        await transport.publish_raw(
            event_id=message.event_id,
            event_type=message.event_type,
            payload=message.payload,
        )

    return OutboxRelay(open_outbox, publish)


def _handle_live_signals(signals: list[LiveSignal]) -> None:
    """Live sync subscriber handler: fan out to this process's SSE clients.
    No DB, no blocking I/O, runs directly on the event loop."""
    get_live_hub().broadcast(signals)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown logic."""

    assert_production_secrets_ok(cfg.security, debug=cfg.debug)
    assert_production_credentials_ok(cfg.init, cfg.database.url, debug=cfg.debug)
    assert_bundled_storage_secret_ok(
        cfg.seaweedfs_secret_key, cfg.compose_profiles, debug=cfg.debug
    )

    # 1. Migrate DB schema (dev only, prod runs migrations via the entrypoint before workers fork)
    if cfg.debug:
        await asyncio.to_thread(run_migrations)

    # 2. Seed initial data
    async with SessionLocal() as db:
        user_repo = SqlAlchemyUserRepository(db)
        admin_settings_repo = SqlAlchemyAdminSettingsRepository(db)
        await InitDatabase(
            user_repo=user_repo,
            admin_settings_repo=admin_settings_repo,
            print_template_repo=SqlAlchemyPrintTemplateRepository(db),
            db=db,
        ).run()
        storage = await admin_settings_repo.get_storage()

    # The local storage adapter reads and writes under this directory.
    if storage.provider == "local" and storage.enabled:
        await asyncio.to_thread(Path(cfg.local_storage.base_dir).mkdir, parents=True, exist_ok=True)

    # 3. Attach DB log handler, from this point log.info/error/... at or above
    # LOG_DB_LEVEL are also queued for log_table and written in the background
    def _persist_logs(entries: list[LogEntry]) -> None:
        with LogSessionLocal() as db:
            persist_log_batch(db, entries)
            db.commit()

    db_log_handler = DatabaseLogHandler(persist_batch=_persist_logs)
    db_log_handler.setLevel(cfg.log_db_level)
    db_log_handler.start()
    log.addHandler(db_log_handler)

    # 5. Start background tasks
    # Every long-lived task is named and supervised by _log_task_completion,
    # so a death is one CRITICAL log record with a traceback, a gauge at 0
    # and a /ready warning rather than silence (see the helper's docstring).
    notification_task = asyncio.create_task(_notification_task(), name="notification-digest")

    # 6. Start event bus workers (consumer groups on the glados:events stream)
    redis_client = get_async_redis_client()
    background_tasks = [
        notification_task,
        # Interval jobs (backup, disk space, retention, PDM poll): each
        # re-reads its settings from the DB on every run, see
        # system_schedule.py and pdm_schedule.py.
        *BackupScheduler().start(),
        *PdmPollScheduler().start(),
        # The bundled meeting notifications, the retention purge of meetings
        # and the nightly sweep of unreferenced meeting files.
        *MeetingScheduler().start(),
        asyncio.create_task(
            EventWorker(
                redis_client, group="notifications", handler=_handle_notification_event
            ).run(),
            name="event-worker:notifications",
        ),
        asyncio.create_task(
            EventWorker(redis_client, group="webhooks", handler=_handle_webhook_event).run(),
            name="event-worker:webhooks",
        ),
        asyncio.create_task(
            EventWorker(redis_client, group="auto_print", handler=_handle_auto_print_event).run(),
            name="event-worker:auto_print",
        ),
        asyncio.create_task(
            EventWorker(redis_client, group="pdm_sync", handler=_handle_pdm_sync_event).run(),
            name="event-worker:pdm_sync",
        ),
        asyncio.create_task(
            EventWorker(redis_client, group="schedule", handler=_handle_schedule_event).run(),
            name="event-worker:schedule",
        ),
        asyncio.create_task(
            run_every(TICK_SECONDS, ScheduleTick(_walk_schedule, _tenant_today), "schedule_tick"),
            name="schedule-tick",
        ),
        asyncio.create_task(
            run_every(PLAN_BASELINE_TICK_SECONDS, _record_plan_baseline, "plan_baseline"),
            name="plan-baseline",
        ),
        asyncio.create_task(
            EventWorker(
                redis_client, group="edp_pictures", handler=_handle_edp_picture_event
            ).run(),
            name="event-worker:edp_pictures",
        ),
    ]

    # 7. Live row-sync: attach change-capture listeners to every SessionLocal
    # session, then start the Pub/Sub subscriber that fans signals out to
    # this process's connected SSE clients.
    register_change_tracking(SessionLocal)
    background_tasks.append(
        asyncio.create_task(
            LiveEventSubscriber(redis_client, handler=_handle_live_signals).run(),
            name="live-subscriber",
        )
    )

    # 8. Transactional outbox: the tripwire that reports a staged event no one
    # committed, then the relay that drains staged rows onto the events stream.
    register_outbox_tripwire(SessionLocal)
    background_tasks.append(asyncio.create_task(_make_outbox_relay().run(), name="outbox-relay"))

    # 9. Trim the events stream past what every consumer group has processed.
    async def _trim_events_stream() -> None:
        await trim_events_stream(redis_client)

    background_tasks.append(
        asyncio.create_task(
            run_every(TRIM_INTERVAL_SECONDS, _trim_events_stream, "events_stream_trim"),
            name="events-stream-trim",
        )
    )

    for task in background_tasks:
        mark_task_running(task.get_name())
        task.add_done_callback(_log_task_completion)

    log.info(f"Glados started. Debug={cfg.debug}")
    yield

    # Shutdown
    get_live_hub().close_all()
    for task in background_tasks:
        task.cancel()
    results = await asyncio.gather(*background_tasks, return_exceptions=True)
    for task, result in zip(background_tasks, results, strict=True):
        if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
            log.error(
                "Background task %r ended with %s during shutdown.",
                task.get_name(),
                result,
                exc_info=result,
            )
    await redis_client.aclose()
    await close_pdm_gateways()
    await close_time_tracking_clients()
    await close_weather_service()
    await close_stock_service_clients()
    await close_eplan_data_portals()
    log.info("Glados shutting down.")
    # Last: everything above may still log. The handler flushes its queue on
    # stop, and is detached before the engines go so nothing reopens a pool.
    log.removeHandler(db_log_handler)
    db_log_handler.stop()
    await engine.dispose()
    log_engine.dispose()


def create_app() -> FastAPI:
    register_all()
    # FastAPI's own docs routes stay off: register_surface_docs serves /docs
    # and /openapi.json behind the same login as the per-surface pages.
    app = FastAPI(
        title="Glados",
        version=VERSION,
        lifespan=lifespan,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )

    # Registered first, so it is innermost and the outer middleware sees a
    # JSON response instead of an unwinding exception.
    app.add_middleware(UnhandledExceptionMiddleware)

    # Just outside it, so it sees the 503 a lost database race answers and
    # runs a request that committed nothing once more, before the audit log
    # and the request log record it once.
    app.add_middleware(LostRaceRetryMiddleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[cfg.domain],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Headers the frontend must be able to read.
        expose_headers=["X-Preview-Warnings", "Content-Disposition", VERSION_HEADER],
    )

    # Audit log, records every write request (and every PAT / API-key call)
    # to the database; see the middleware's docstring.
    app.add_middleware(DatabaseLoggingMiddleware)

    # Wraps the audit log and everything below it: mints the request ID, sets
    # the context vars and logs every request. Only the security headers, the
    # version header and the metrics middleware sit outside it.
    app.add_middleware(RequestContextMiddleware)

    # Outside every layer that sets headers, so it sees each header they set
    # and never overrides an existing one.
    app.add_middleware(SecurityHeadersMiddleware)

    # Just inside the metrics middleware, so every `pat` response carries
    # the backend version, the 401 of a missing token and the 500 of a crash
    # included.
    app.add_middleware(VersionHeaderMiddleware)

    # Domain exception → HTTP response mapping
    register_exception_handlers(app)

    # Adds its own middleware, so it must come before the routers.
    instrument(app)

    app.include_router(auth_router)
    app.include_router(web_router)
    app.include_router(pat_router)
    app.include_router(key_router)
    app.include_router(public_router)

    # The MCP surface for AI agents, one route for every method the
    # transport answers. Bearer tokens only, see AgentAuthMiddleware.
    app.router.routes.append(
        Route(
            API_MCP, build_agent_app(), methods=["GET", "POST", "DELETE"], include_in_schema=False
        )
    )

    # Swagger UI pages: /docs and /docs/web, /docs/pat, /docs/key, behind a
    # login outside debug mode.
    register_surface_docs(app, debug=cfg.debug)

    # Health check (no auth, used by nginx and docker healthcheck)
    # async so a liveness probe never queues behind busy threadpool workers.
    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": VERSION}

    # Readiness pings the database and Redis. Docker's health check stays on
    # /health, because restarting on a dead Redis would fix nothing. The
    # backup and stopped background task warnings ride along without
    # changing the status.
    @app.get("/ready", include_in_schema=False)
    async def ready() -> JSONResponse:
        ok, checks = await readiness_report()
        warnings = await backup_warnings_report() + await background_task_warnings_report()
        return JSONResponse(
            {"status": "ok" if ok else "fail", "checks": checks, "warnings": warnings},
            status_code=200 if ok else 503,
        )

    # Prometheus scrape endpoint (no auth; not proxied by the frontend's
    # nginx, reachable only on the docker network).
    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return await metrics_response()

    return app


app = create_app()
