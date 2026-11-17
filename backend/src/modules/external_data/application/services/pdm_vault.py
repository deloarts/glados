"""
Small helpers the poller, the single-file refresh, validation, write-back and
the document sync share about the configured vault and the files in it: the
vault id lookup, the vault name comparison, the per-file lock, the file
extension rule and the sync run entry for one PDM file.
"""

from contextlib import AbstractAsyncContextManager
from contextlib import nullcontext
from pathlib import Path

from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRunEntry
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.pdm_file_lock_port import IPdmFileLock
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


async def fetch_vault_id(session: PdmSessionService) -> str:
    """The vault's id as the Web API reports it."""

    async def _vault_id(gw: IPdmGateway, token: str) -> str:
        return (await gw.vault_info(token)).vault_id

    return await session.call(_vault_id)


async def resolve_and_store_vault_id(
    settings: AdminPdmSettings,
    session: PdmSessionService,
    admin_settings: IExternalDataSettingsRepository,
    uow: IUnitOfWork,
) -> str:
    """The stored vault id, or, before the first sync has stored one, the id
    fetched from the Web API, saved and committed so later runs skip the
    call."""
    vault_id = settings.vault_id
    if not vault_id:
        vault_id = await fetch_vault_id(session)
        await admin_settings.save_pdm_vault_id(vault_id)
        await uow.commit()
    return vault_id


def vault_name_matches(requested: str, configured: str) -> bool:
    """True when both name the same vault, ignoring surrounding whitespace
    and case."""
    return requested.strip().lower() == configured.strip().lower()


def hold_file(file_lock: IPdmFileLock | None, file_id: int) -> AbstractAsyncContextManager[None]:
    """The file's lock, or no lock at all where none is wired."""
    if file_lock is None:
        return nullcontext()
    return file_lock.hold(file_id)


def file_extension(name: str) -> str:
    """The file name's extension, lower case and without the dot, or an
    empty string when it has none."""
    return Path(name).suffix.lstrip(".").lower()


def sync_run_entry(
    run_id: int,
    vault_id: str,
    obj: PdmObjectInfo,
    kind: str | None,
    action: str,
    item_id: int | None,
    message: str,
) -> PdmSyncRunEntry:
    """A new sync run entry for one PDM file, stamped now."""
    return PdmSyncRunEntry(
        id=0,
        run_id=run_id,
        vault_id=vault_id,
        file_id=obj.id,
        name=obj.name,
        path=obj.path,
        kind=kind,
        action=action,
        item_id=item_id,
        message=message,
        created_at=now_utc(),
    )
