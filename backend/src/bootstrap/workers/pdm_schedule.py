"""
PdmPollScheduler: one interval job (src/modules/platform/infrastructure/interval_task.py),
60s, mirroring BackupScheduler (system_schedule.py): immediate first tick,
then every 60s after the previous tick finished, so a slow tick never piles
up behind the next one. Every tick opens its own SessionLocal(), re-reads settings from
the DB (RunPdmPollIfDue does that itself) and builds the whole PDM use
case chain from scratch: nothing about the vault, the watched folders or
the poll interval is cached across ticks anywhere in this class.

build_ingest_pdm_file, build_pdm_document_sync and build_pdm_thumbnails are
exported (not private) because _handle_pdm_sync_event in main.py needs the
exact same wiring for the single-file refresh path (RefreshPdmFile);
duplicating that construction in two places would drift the moment one of
these use cases' dependencies changes. build_pdm_thumbnails resolves the
storage adapter itself (StorageMigrationError -> no storage, same
fail-open shape _handle_auto_print_event uses) since thumbnails, like a
docket's images, must never take the whole tick down just because storage
is misconfigured.

Every tick also wires a ReconcilePdmVault and hands it to RunPdmPollIfDue,
which runs it before the poll-interval check whenever an admin has queued
a reconciliation report (AdminPdmSettings.reconcile_requested_deep). See
that use case's own docstring for why this lives in the same tick rather
than a separate scheduler job.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.repositories.article_group_repository import (
    SqlAlchemyArticleGroupRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_file_repository import (
    SqlAlchemyBoughtItemFileRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_repository.item import (
    SqlAlchemyBoughtItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.customer_repository import (
    SqlAlchemyCustomerRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.fabrication_method_repository import (
    SqlAlchemyFabricationMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.inspection_method_repository import (
    SqlAlchemyInspectionMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.item_picture_repository import (
    SqlAlchemyItemPictureRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_file_repository import (
    SqlAlchemyMadeItemFileRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.part_number_registry_repository import (
    SqlAlchemyPartNumberRegistryRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_repository import (
    SqlAlchemySourceItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.supplier_repository import (
    SqlAlchemySupplierRepository,
)
from src.modules.catalogue.application.services.item_picture_store import ItemPictureStore
from src.modules.catalogue.application.use_cases.bought_item.create_bought_item import (
    CreateBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.upload_bought_item_file import (
    UploadBoughtItemFile,
)
from src.modules.catalogue.application.use_cases.made_item.create_made_item import CreateMadeItem
from src.modules.catalogue.application.use_cases.made_item.create_made_item_revision import (
    CreateMadeItemRevision,
)
from src.modules.catalogue.application.use_cases.made_item.upload_made_item_file import (
    UploadMadeItemFile,
)
from src.modules.external_data.adapters.outbound.external.pdm.factory import create_pdm_gateway
from src.modules.external_data.adapters.outbound.persistence.pdm_file_lock import (
    SqlAlchemyPdmFileLock,
)
from src.modules.external_data.adapters.outbound.persistence.pdm_poll_lock import (
    SqlAlchemyPdmPollLock,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.external_data_settings_repository import (
    SqlAlchemyExternalDataSettingsRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_document_link_repository import (
    SqlAlchemyPdmDocumentLinkRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_file_snapshot_repository import (
    SqlAlchemyPdmFileSnapshotRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_folder_poll_state_repository import (
    SqlAlchemyPdmFolderPollStateRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_reconciliation_finding_repository import (
    SqlAlchemyPdmReconciliationFindingRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_sync_run_repository import (
    SqlAlchemyPdmSyncRunRepository,
)
from src.modules.external_data.application.services.pdm_cad_source import PdmCadSource
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.services.pdm_writeback import PdmWriteBack
from src.modules.external_data.application.use_cases.pdm.ingest_pdm_file import IngestPdmFile
from src.modules.external_data.application.use_cases.pdm.pdm_documents import PdmDocumentSync
from src.modules.external_data.application.use_cases.pdm.pdm_documents import PdmThumbnails
from src.modules.external_data.application.use_cases.pdm.poll_pdm_vault import PollPdmVault
from src.modules.external_data.application.use_cases.pdm.reconcile_pdm_vault import (
    ReconcilePdmVault,
)
from src.modules.external_data.application.use_cases.pdm.run_pdm_poll_if_due import RunPdmPollIfDue
from src.modules.external_data.ports.outbound.pdm_file_lock_port import IPdmFileLock
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    IPdmSyncRunRepository,
)
from src.modules.platform.adapters.outbound.external.storage.factory import create_storage_adapter
from src.modules.platform.adapters.outbound.persistence.event_outbox import OutboxEventBus
from src.modules.platform.adapters.outbound.persistence.repositories.user_pdm_link_repository import (
    SqlAlchemyUserPdmLinkRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.adapters.outbound.persistence.session import engine
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.domain.exceptions import StorageMigrationError
from src.modules.platform.infrastructure.interval_task import run_every
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import IStoragePort

_TICK_INTERVAL_SECONDS = 60


def build_ingest_pdm_file(db: AsyncSession, session: PdmSessionService) -> IngestPdmFile:
    """Wires IngestPdmFile and the three create-use-cases it reuses, all
    sharing `db` (one session per tick/event) and one transactional
    event bus + unit of work, matching how deps/items.py wires the same
    three use cases for the web/PAT surfaces. `session` is the tick/
    event's own PdmSessionService, shared the same way build_pdm_document_
    sync/build_pdm_thumbnails share it: IngestPdmFile needs it for
    IPdmGateway.file_transitions (PDM releaser attribution)."""
    made_item_repo = SqlAlchemyMadeItemRepository(db)
    bought_item_repo = SqlAlchemyBoughtItemRepository(db)
    article_group_repo = SqlAlchemyArticleGroupRepository(db)
    source_item_repo = SqlAlchemySourceItemRepository(db)
    customer_repo = SqlAlchemyCustomerRepository(db)
    supplier_repo = SqlAlchemySupplierRepository(db)
    fabrication_method_repo = SqlAlchemyFabricationMethodRepository(db)
    inspection_method_repo = SqlAlchemyInspectionMethodRepository(db)
    admin_settings_repo = SqlAlchemyExternalDataSettingsRepository(db)
    snapshot_repo = SqlAlchemyPdmFileSnapshotRepository(db)
    user_repo = SqlAlchemyUserRepository(db)
    part_number_registry = SqlAlchemyPartNumberRegistryRepository(db)
    event_bus = OutboxEventBus(db)
    uow = SqlAlchemyUnitOfWork(db)

    create_made_item = CreateMadeItem(
        made_item_repo,
        article_group_repo,
        bought_item_repo,
        source_item_repo,
        fabrication_method_repo,
        inspection_method_repo,
        admin_settings_repo,
        customer_repo=customer_repo,
        part_number_registry=part_number_registry,
        event_bus=event_bus,
        uow=uow,
        cad_source=PdmCadSource(admin_settings_repo),
    )
    create_made_item_revision = CreateMadeItemRevision(
        made_item_repo,
        article_group_repo,
        bought_item_repo,
        source_item_repo,
        fabrication_method_repo,
        inspection_method_repo,
        admin_settings_repo,
        customer_repo=customer_repo,
        part_number_registry=part_number_registry,
        event_bus=event_bus,
        uow=uow,
    )
    create_bought_item = CreateBoughtItem(
        bought_item_repo,
        supplier_repo,
        article_group_repo,
        admin_settings_repo,
        part_number_registry=part_number_registry,
        event_bus=event_bus,
        uow=uow,
        cad_source=PdmCadSource(admin_settings_repo),
    )

    return IngestPdmFile(
        made_item_repo,
        bought_item_repo,
        article_group_repo,
        source_item_repo,
        supplier_repo,
        fabrication_method_repo,
        inspection_method_repo,
        admin_settings_repo,
        snapshot_repo,
        user_repo,
        SqlAlchemyUserPdmLinkRepository(db),
        create_made_item=create_made_item,
        create_made_item_revision=create_made_item_revision,
        create_bought_item=create_bought_item,
        customer_repo=customer_repo,
        part_number_registry=part_number_registry,
        event_bus=event_bus,
        uow=uow,
        session=session,
    )


async def build_pdm_document_sync(db: AsyncSession, session: PdmSessionService) -> PdmDocumentSync:
    """Wires PdmDocumentSync, sharing `db` and `session` with the rest of
    the tick/event's use case chain. The two upload use cases are built
    WITHOUT `admin_settings_repo` (unlike deps/items.py's web-facing
    instances) so the "only the newest revision is editable" UI rule
    never blocks the system actor from attaching a document to an older,
    historical revision, the same exemption docs/reference/field-ownership.md
    section 6 gives every system-actor write. They do get the shared unit
    of work, so the read transaction ends before image processing, hashing
    and the storage upload; PdmDocumentSync.sync_one reaches the upload
    with no pending writes, only reads."""
    made_item_repo = SqlAlchemyMadeItemRepository(db)
    bought_item_repo = SqlAlchemyBoughtItemRepository(db)
    storage = await _build_storage(db)
    uow = SqlAlchemyUnitOfWork(db)
    picture_store = (
        ItemPictureStore(SqlAlchemyItemPictureRepository(db), storage) if storage else None
    )
    return PdmDocumentSync(
        session,
        SqlAlchemyExternalDataSettingsRepository(db),
        made_item_repo,
        bought_item_repo,
        SqlAlchemyPdmFileSnapshotRepository(db),
        SqlAlchemyPdmDocumentLinkRepository(db),
        SqlAlchemyUserRepository(db),
        upload_made_item_file=UploadMadeItemFile(
            made_item_repo, SqlAlchemyMadeItemFileRepository(db), storage, uow=uow
        ),
        upload_bought_item_file=UploadBoughtItemFile(
            bought_item_repo, SqlAlchemyBoughtItemFileRepository(db), storage, uow=uow
        ),
        picture_store=picture_store,
        uow=uow,
    )


async def build_pdm_thumbnails(
    db: AsyncSession, session: PdmSessionService, run_repo: IPdmSyncRunRepository
) -> PdmThumbnails:
    """Wires PdmThumbnails the same way build_pdm_document_sync wires its
    own storage dependency."""
    picture_repo = SqlAlchemyItemPictureRepository(db)
    storage = await _build_storage(db)
    return PdmThumbnails(
        session,
        SqlAlchemyExternalDataSettingsRepository(db),
        picture_repo,
        ItemPictureStore(picture_repo, storage) if storage else None,
        SqlAlchemyUserRepository(db),
        run_repo,
        SqlAlchemyUnitOfWork(db),
    )


async def _build_storage(db: AsyncSession) -> IStoragePort | None:
    """Same fail-open shape main.py's _handle_auto_print_event uses: a
    misconfigured storage backend must never take a PDM tick down, it
    just means documents/thumbnails are skipped for that tick."""
    admin_settings_repo = SqlAlchemyExternalDataSettingsRepository(db)
    storage_settings = await admin_settings_repo.get_storage()
    if not storage_settings.enabled:
        return None
    try:
        return create_storage_adapter(storage_settings)
    except StorageMigrationError:
        return None


async def _build_poll(
    db: AsyncSession,
    *,
    worker_factory: Callable[[], AbstractAsyncContextManager[PollPdmVault]] | None = None,
    file_lock: IPdmFileLock | None = None,
) -> PollPdmVault:
    """Wires PollPdmVault on `db`. The tick's own poller gets the worker
    factory and the file lock; a worker it hands files to gets neither,
    since it only ever processes the files it is given."""
    admin_settings_repo = SqlAlchemyExternalDataSettingsRepository(db)
    made_item_repo = SqlAlchemyMadeItemRepository(db)
    bought_item_repo = SqlAlchemyBoughtItemRepository(db)
    session = PdmSessionService(
        repo=admin_settings_repo,
        gateway_factory=create_pdm_gateway,
        uow=SqlAlchemyUnitOfWork(db),
    )
    run_repo = SqlAlchemyPdmSyncRunRepository(db)
    return PollPdmVault(
        session=session,
        admin_settings_repo=admin_settings_repo,
        snapshot_repo=SqlAlchemyPdmFileSnapshotRepository(db),
        made_item_repo=made_item_repo,
        bought_item_repo=bought_item_repo,
        ingest=build_ingest_pdm_file(db, session),
        write_back=PdmWriteBack(
            session=session,
            settings_repo=admin_settings_repo,
            made_repo=made_item_repo,
            bought_repo=bought_item_repo,
            run_repo=run_repo,
        ),
        document_sync=await build_pdm_document_sync(db, session),
        thumbnails=await build_pdm_thumbnails(db, session, run_repo),
        run_repo=run_repo,
        folder_poll_state_repo=SqlAlchemyPdmFolderPollStateRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
        worker_factory=worker_factory,
        file_lock=file_lock,
    )


@asynccontextmanager
async def _poll_worker() -> AsyncIterator[PollPdmVault]:
    """One parallel ingest worker for a poll run, on its own session."""
    async with SessionLocal() as db:
        yield await _build_poll(db)


class PdmPollScheduler:
    def start(self) -> list[asyncio.Task[None]]:
        """Starts the poll job as a background task and returns it, for the
        lifespan to supervise and cancel on shutdown."""
        return [
            asyncio.create_task(
                run_every(_TICK_INTERVAL_SECONDS, self._tick, "pdm_poll_tick"),
                name="pdm-poll",
            )
        ]

    async def _tick(self) -> None:
        try:
            async with SessionLocal() as db:
                admin_settings_repo = SqlAlchemyExternalDataSettingsRepository(db)
                snapshot_repo = SqlAlchemyPdmFileSnapshotRepository(db)
                made_item_repo = SqlAlchemyMadeItemRepository(db)
                bought_item_repo = SqlAlchemyBoughtItemRepository(db)
                session = PdmSessionService(
                    repo=admin_settings_repo,
                    gateway_factory=create_pdm_gateway,
                    uow=SqlAlchemyUnitOfWork(db),
                )
                run_repo = SqlAlchemyPdmSyncRunRepository(db)
                poll = await _build_poll(
                    db, worker_factory=_poll_worker, file_lock=SqlAlchemyPdmFileLock(engine)
                )
                reconcile = ReconcilePdmVault(
                    session=session,
                    admin_settings_repo=admin_settings_repo,
                    snapshot_repo=snapshot_repo,
                    made_item_repo=made_item_repo,
                    bought_item_repo=bought_item_repo,
                    document_link_repo=SqlAlchemyPdmDocumentLinkRepository(db),
                    part_number_registry=SqlAlchemyPartNumberRegistryRepository(db),
                    supplier_repo=SqlAlchemySupplierRepository(db),
                    run_repo=run_repo,
                    finding_repo=SqlAlchemyPdmReconciliationFindingRepository(db),
                    uow=SqlAlchemyUnitOfWork(db),
                )
                await RunPdmPollIfDue(
                    admin_settings_repo=admin_settings_repo,
                    lock=SqlAlchemyPdmPollLock(engine),
                    poll=poll,
                    reconcile=reconcile,
                    run_repo=run_repo,
                    uow=SqlAlchemyUnitOfWork(db),
                ).execute()
        except Exception:
            # A tick must never kill the recurring job, same fail-open
            # shape as BackupScheduler._tick: PollPdmVault itself already
            # persisted last_poll_error for whatever it managed to run
            # before failing, this is just the "still alive" log line.
            log.exception("PdmPollScheduler: tick failed.")
