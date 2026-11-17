"""
The reconciliation report: unlike PollPdmVault, this never ingests anything;
it only compares what the database already holds (pdm_file_snapshot, the
made/bought catalogues, part_number_registry, pdm_document_link) against
itself and, in deep mode, against a handful of the vault's own datacard
variables, and records what it finds as PdmReconciliationFinding rows.
Quick mode is pure DB reads; deep mode additionally calls the vault once
per linked made/bought file to check write-back drift.

Every category's actual logic lives in application.services.
pdm_reconciliation as a pure function operating on data already loaded in
bulk (see that module's docstring for why, including the three lifecycle-
status categories: status_mismatch, replaced_without_successor,
successor_without_replaced, part_number_drift); this use case's own
job is loading that data, calling those functions, handling the two
categories that need a point lookup per candidate instead of bulk data
(`unclaimed_match`, `_find_unclaimed_matches` below) or a vault call per
file (`writeback_drift`, `_find_writeback_drift`), and persisting the
result.

Runs as a PdmSyncRun the same way PollPdmVault does (trigger
`reconciliation`, started before anything else runs so a crash mid-run
still leaves a visible row), but with `folders_walked` and the poll-style
counters left at zero: a reconciliation run's own outcome is entirely in
its findings and the run's `summary` line (counts per category), not in
files-seen/changed/ingested counters that mean nothing for a comparison
pass. An unreadable datacard during the deep write-back check is recorded
as its own `writeback_drift` finding (severity info, the error text as the
message) rather than aborting the run: see
application.services.pdm_reconciliation and this module's
_find_writeback_drift. A failure that aborts the whole run (vault
unreachable while resolving vault_id, a database error) is still recorded
on the run itself (`error`), mirroring PollPdmVault.execute.
"""

import json
from collections import defaultdict
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.part_number_registry import PartNumberRegistryEntry
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IMadeItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IPartNumberRegistryCadStore
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.external_data.application.services.pdm_field_resolution import resolve_manufacturer
from src.modules.external_data.application.services.pdm_reconciliation import CadRowRef
from src.modules.external_data.application.services.pdm_reconciliation import ReconciliationFinding
from src.modules.external_data.application.services.pdm_reconciliation import find_document_missing
from src.modules.external_data.application.services.pdm_reconciliation import (
    find_document_unmatched,
)
from src.modules.external_data.application.services.pdm_reconciliation import (
    find_duplicate_snapshot_part_numbers,
)
from src.modules.external_data.application.services.pdm_reconciliation import (
    find_items_without_registry_entry,
)
from src.modules.external_data.application.services.pdm_reconciliation import find_kind_mismatches
from src.modules.external_data.application.services.pdm_reconciliation import find_orphaned_cad_rows
from src.modules.external_data.application.services.pdm_reconciliation import (
    find_orphaned_registry_entries,
)
from src.modules.external_data.application.services.pdm_reconciliation import find_part_number_drift
from src.modules.external_data.application.services.pdm_reconciliation import (
    find_replaced_without_successor,
)
from src.modules.external_data.application.services.pdm_reconciliation import find_revision_lag
from src.modules.external_data.application.services.pdm_reconciliation import find_status_mismatches
from src.modules.external_data.application.services.pdm_reconciliation import find_stuck_files
from src.modules.external_data.application.services.pdm_reconciliation import (
    find_successor_without_replaced,
)
from src.modules.external_data.application.services.pdm_reconciliation import (
    index_snapshots_by_file,
)
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.services.pdm_variables import NO_FILE_LEVEL_CONFIGURATION
from src.modules.external_data.application.services.pdm_variables import map_variables
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.entities.pdm_reconciliation_finding import (
    PdmReconciliationFinding,
)
from src.modules.external_data.domain.entities.pdm_sync_run import SYNC_RUN_RETENTION
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.value_objects.pdm_reconciliation_category import (
    PdmReconciliationCategory,
)
from src.modules.external_data.domain.value_objects.pdm_reconciliation_severity import (
    PdmReconciliationSeverity,
)
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCard
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmVaultInfo
from src.modules.external_data.ports.outbound.repositories.pdm_document_link_repository import (
    IPdmDocumentLinkRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_reconciliation_finding_repository import (
    IPdmReconciliationFindingRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    IPdmSyncRunRepository,
)
from src.modules.platform.application.services.paging import fetch_all
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc

# How many CAD-owned rows list_cad_items_with_links pages through at a
# time, large enough to keep the query count sane and small enough that one
# page is never a meaningfully sized load.
_PAGE_SIZE = 200


@dataclass
class PdmReconciliationSummary:
    counts: dict[str, int]  # PdmReconciliationCategory -> total files affected


class ReconcilePdmVault:
    def __init__(
        self,
        session: PdmSessionService,
        admin_settings_repo: IExternalDataSettingsRepository,
        snapshot_repo: IPdmFileSnapshotRepository,
        made_item_repo: IMadeItemCadStore,
        bought_item_repo: IBoughtItemCadStore,
        document_link_repo: IPdmDocumentLinkRepository,
        part_number_registry: IPartNumberRegistryCadStore,
        supplier_repo: ISupplierQueries,
        run_repo: IPdmSyncRunRepository,
        finding_repo: IPdmReconciliationFindingRepository,
        uow: IUnitOfWork,
    ) -> None:
        self._session = session
        self._admin_settings = admin_settings_repo
        self._snapshots = snapshot_repo
        self._made_items = made_item_repo
        self._bought_items = bought_item_repo
        self._document_links = document_link_repo
        self._registry = part_number_registry
        self._suppliers = supplier_repo
        self._runs = run_repo
        self._findings = finding_repo
        self._uow = uow

    async def execute(self, deep: bool) -> PdmReconciliationSummary:
        started_at = now_utc()
        run = await self._runs.start(
            PdmSyncRun(
                id=0,
                started_at=started_at,
                finished_at=None,
                trigger=PdmSyncTrigger.RECONCILIATION,
                files_seen=0,
                changed=0,
                ingested=0,
                skipped=0,
                conflicts=0,
                errors=0,
                missing=0,
                error=None,
                summary=None,
                folders_walked=0,
            )
        )
        await self._uow.commit()
        try:
            counts = await self._run(run, deep=deep, started_at=started_at)
        except Exception as exc:
            await self._finish_run(run, {}, error=str(exc))
            raise
        await self._finish_run(run, counts, error=None)
        return PdmReconciliationSummary(counts=counts)

    async def _run(self, run: PdmSyncRun, *, deep: bool, started_at: datetime) -> dict[str, int]:
        settings = await self._admin_settings.get_pdm()

        vault_id = settings.vault_id
        if not vault_id:

            async def _vault_info(gw: IPdmGateway, token: str) -> PdmVaultInfo:
                return await gw.vault_info(token)

            vault_info = await self._session.call(_vault_info)
            vault_id = vault_info.vault_id
            await self._admin_settings.save_pdm_vault_id(vault_id)
            await self._uow.commit()

        snapshots = await self._snapshots.get_all_for_vault(vault_id)
        snapshots_by_key = index_snapshots_by_file(snapshots)

        made_rows = await self._load_cad_rows(
            self._made_items.list_cad_items_with_links, kind="made"
        )
        bought_rows = await self._load_cad_rows(
            self._bought_items.list_cad_items_with_links, kind="bought"
        )
        all_rows = made_rows + bought_rows

        registry_entries = await self._registry.all_entries()
        registered_kind_by_part_number = {e.part_number: e.kind.value for e in registry_entries}
        live_made, live_bought = await self._live_part_number_sets(registry_entries)

        document_links = await self._document_links.all_for_vault(vault_id)

        findings: list[ReconciliationFinding] = []
        findings += find_orphaned_cad_rows(all_rows, snapshots_by_key)
        findings += find_revision_lag(all_rows, snapshots_by_key)
        findings += find_kind_mismatches(all_rows, snapshots_by_key)
        findings += find_status_mismatches(all_rows, snapshots_by_key, settings)
        findings += find_replaced_without_successor(all_rows)
        findings += find_successor_without_replaced(all_rows)
        findings += find_part_number_drift(all_rows, snapshots_by_key)
        findings += find_stuck_files(
            snapshots, stuck_after_days=settings.stuck_after_days, now=started_at
        )
        findings += find_duplicate_snapshot_part_numbers(snapshots)
        findings += find_orphaned_registry_entries(
            registry_entries,
            live_made_part_numbers=live_made,
            live_bought_part_numbers=live_bought,
        )
        findings += find_items_without_registry_entry(all_rows, registered_kind_by_part_number)
        findings += find_document_missing(document_links, snapshots_by_key)
        findings += find_document_unmatched(snapshots)
        findings += await self._find_unclaimed_matches(snapshots, settings)
        if deep:
            findings += await self._find_writeback_drift(vault_id, snapshots, settings)

        counts: dict[str, int] = defaultdict(int)
        for finding in findings:
            counts[finding.category] += finding.count

        now = now_utc()
        entities = [
            PdmReconciliationFinding(
                id=0,
                run_id=run.id,
                category=PdmReconciliationCategory(finding.category),
                severity=PdmReconciliationSeverity(finding.severity),
                kind=finding.kind,
                item_id=finding.item_id,
                file_id=finding.file_id,
                part_number=finding.part_number,
                revision=finding.revision,
                message=finding.message,
                count=finding.count,
                created_at=now,
            )
            for finding in findings
        ]
        if entities:
            await self._findings.add_many(entities)
        await self._uow.commit()
        return dict(counts)

    # ── Bulk loading ─────────────────────────────────────────────────

    async def _load_cad_rows(
        self,
        page: Callable[
            [int | None, int | None], Awaitable[tuple[int, Sequence[MadeItem | BoughtItem]]]
        ],
        *,
        kind: str,
    ) -> list[CadRowRef]:
        items = await fetch_all(page, _PAGE_SIZE)
        return [
            CadRowRef(
                item_id=item.id,
                kind=kind,
                vault_id=item.vault_id,
                pdm_file_id=item.pdm_file_id,
                pdm_file_version=item.pdm_file_version,
                part_number=item.part_number,
                revision=getattr(item, "revision", None),
                status=item.status.value,
                successor_item_id=item.successor_item_id,
            )
            for item in items
        ]

    async def _live_part_number_sets(
        self, entries: list[PartNumberRegistryEntry]
    ) -> tuple[frozenset[str], frozenset[str]]:
        """One batch existence check per kind against its own catalogue,
        via existing_part_numbers, instead of one get_revisions/
        get_by_part_number call per registry entry: bounded by the
        registry's own size, not the catalogue's, so this stays
        proportionate even for a large catalogue. See
        find_orphaned_registry_entries' docstring for why this should
        normally find nothing."""
        made_part_numbers = [e.part_number for e in entries if e.kind == "made"]
        bought_part_numbers = [e.part_number for e in entries if e.kind != "made"]
        live_made = await self._made_items.existing_part_numbers(made_part_numbers)
        live_bought = await self._bought_items.existing_part_numbers(bought_part_numbers)
        return frozenset(live_made), frozenset(live_bought)

    # ── unclaimed_match (needs a point lookup per candidate) ──────────

    async def _find_unclaimed_matches(
        self, snapshots: list[PdmFileSnapshot], settings: AdminPdmSettings
    ) -> list[ReconciliationFinding]:
        """A parked bought-kind conflict (parked_payload set, never
        linked) whose identity, read the same way IngestPdmFile itself
        would, now matches an unlinked bought item via
        IBoughtItemCadStore.find_claim_candidate, the same rule ingest
        uses, so this is exactly "what the next successful ingest attempt
        of this file would claim", surfaced without re-reading the vault."""
        findings: list[ReconciliationFinding] = []
        variable_map = settings.bought_item_variable_map
        for snapshot in snapshots:
            if snapshot.kind != "bought" or snapshot.item_id is not None:
                continue
            if not snapshot.parked_payload:
                continue
            mapped = map_variables("bought", variable_map, snapshot.parked_payload)
            gtin = (mapped.get("gtin") or "").strip() or None
            order_code_1 = (mapped.get("order_code_1") or "").strip() or None
            manufacturer_id, _ = await resolve_manufacturer(mapped, self._suppliers)
            if gtin is None and (manufacturer_id is None or order_code_1 is None):
                continue
            candidate = await self._bought_items.find_claim_candidate(
                gtin=gtin, manufacturer_id=manufacturer_id, order_code_1=order_code_1
            )
            if candidate is None:
                continue
            findings.append(
                ReconciliationFinding(
                    category=PdmReconciliationCategory.UNCLAIMED_MATCH.value,
                    severity=PdmReconciliationSeverity.INFO.value,
                    kind="bought",
                    item_id=candidate.id,
                    file_id=snapshot.file_id,
                    part_number=mapped.get("part_number") or snapshot.part_number,
                    revision=None,
                    message=(
                        f"Bought item #{candidate.id} already matches this parked PDM "
                        "file and would be claimed on the next successful ingest"
                    ),
                )
            )
        return findings

    # ── writeback_drift (deep mode only, one vault call per file) ────

    async def _find_writeback_drift(
        self, vault_id: str, snapshots: list[PdmFileSnapshot], settings: AdminPdmSettings
    ) -> list[ReconciliationFinding]:
        """Reads the `glados_ids` write-back variable (application.
        services.pdm_writeback.PdmWriteBack) off every linked made/bought
        file's own datacard and compares it against what Glados actually
        has. An unmapped variable is not checked (write-back may simply be
        disabled for this vault); an unreadable card or any other vault
        error becomes its own finding (severity info, the error text)
        rather than aborting the run: deep mode tolerates a per-file
        failure the same way quick mode tolerates a missing snapshot."""
        findings: list[ReconciliationFinding] = []
        for snapshot in snapshots:
            if snapshot.kind not in ("made", "bought") or snapshot.item_id is None:
                continue
            variable_map = (
                settings.made_item_variable_map
                if snapshot.kind == "made"
                else settings.bought_item_variable_map
            )
            variable_name = (variable_map.get("glados_ids") or "").strip()
            if not variable_name:
                continue

            async def fetch_card(
                gw: IPdmGateway, token: str, snapshot: PdmFileSnapshot = snapshot
            ) -> PdmDataCard:
                return await gw.get_datacard(
                    token, snapshot.file_id, snapshot.version, snapshot.parent_folder_id
                )

            try:
                card = await self._session.call(fetch_card)
                if not any(c.name == "@" for c in card.configurations):
                    message = NO_FILE_LEVEL_CONFIGURATION
                    severity = PdmReconciliationSeverity.INFO.value
                    findings.append(
                        ReconciliationFinding(
                            category=PdmReconciliationCategory.WRITEBACK_DRIFT.value,
                            severity=severity,
                            kind=snapshot.kind,
                            item_id=snapshot.item_id,
                            file_id=snapshot.file_id,
                            part_number=snapshot.part_number,
                            revision=snapshot.revision,
                            message=message,
                        )
                    )
                    continue
                actual_raw = self._read_variable(card, variable_name)
                expected_raw = await self._expected_glados_ids(
                    vault_id, snapshot.file_id, snapshot.kind
                )
                if actual_raw is None:
                    message = f"datacard has no {variable_name!r} variable"
                    severity = PdmReconciliationSeverity.INFO.value
                elif self._safe_json(actual_raw) != self._safe_json(expected_raw):
                    message = "Glados.Ids on the datacard differs from what Glados has"
                    severity = PdmReconciliationSeverity.WARNING.value
                else:
                    continue
            except Exception as exc:
                log.warning(
                    "PDM reconciliation: deep write-back check %s/%s failed: %s",
                    vault_id,
                    snapshot.file_id,
                    exc,
                )
                message = str(exc)
                severity = PdmReconciliationSeverity.INFO.value
            findings.append(
                ReconciliationFinding(
                    category=PdmReconciliationCategory.WRITEBACK_DRIFT.value,
                    severity=severity,
                    kind=snapshot.kind,
                    item_id=snapshot.item_id,
                    file_id=snapshot.file_id,
                    part_number=snapshot.part_number,
                    revision=snapshot.revision,
                    message=message,
                )
            )
        return findings

    async def _expected_glados_ids(self, vault_id: str, file_id: int, kind: str) -> str:
        """Duplicates PdmWriteBack._build_glados_ids on purpose rather than
        importing that private method: both compute "every non-deleted
        Glados row of the family" the same way, but keeping them separate
        means a future change to one is not silently also a change to the
        other's expectation of what the vault should hold."""
        if kind == "made":
            family = await self._made_items.get_family_by_pdm_file(vault_id, file_id)
            entries = [
                {
                    "revision": item.revision,
                    "public_id": str(item.public_id),
                    "pdm_version": item.pdm_file_version,
                }
                for item in family
            ]
        else:
            bought = await self._bought_items.get_by_pdm_file(vault_id, file_id)
            entries = (
                [
                    {
                        "revision": None,
                        "public_id": str(bought.public_id),
                        "pdm_version": bought.pdm_file_version,
                    }
                ]
                if bought is not None
                else []
            )
        return json.dumps(entries)

    @staticmethod
    def _read_variable(card: PdmDataCard, name: str) -> str | None:
        """The named variable's value off the "@" file-level configuration
        only. Callers check for that configuration's presence themselves
        (see _find_writeback_drift's own NO_FILE_LEVEL_CONFIGURATION
        branch) before ever reaching here, since a missing "@" card and an
        "@" card simply missing this one variable are reported as two
        different findings."""
        configuration = next((c for c in card.configurations if c.name == "@"), None)
        if configuration is None:
            return None
        for variable in configuration.variables:
            if variable.name == name:
                return variable.value
        return None

    @staticmethod
    def _safe_json(text: str) -> object:
        try:
            return json.loads(text)
        except (TypeError, ValueError):
            # Garbage on the card never accidentally compares equal to a
            # well-formed expected value. It still differs, which is
            # exactly what should be reported.
            return text

    async def _finish_run(self, run: PdmSyncRun, counts: dict[str, int], error: str | None) -> None:
        run.finished_at = now_utc()
        run.error = error
        run.summary = self._format_summary(counts)
        await self._runs.finish(run)
        await self._uow.commit()
        await self._runs.prune(now_utc() - SYNC_RUN_RETENTION)
        await self._uow.commit()

    @staticmethod
    def _format_summary(counts: dict[str, int]) -> str:
        if not counts:
            return "no findings"
        return ", ".join(f"{count} {category}" for category, count in sorted(counts.items()))
