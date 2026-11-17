"""Pre-release validation: a read-only dry run of IngestPdmFile's rules for
one file, so an engineer sees what ingest would do before releasing. The
behaviour, including `reasons` versus `pending_pdm`, is described in
docs/reference/pdm-ingest.md section 8.

It reuses ingest's own resolution helpers so the two never drift, but
reports every failing rule instead of the first, skips the version and
workflow-state checks, and finds existing rows by identity because the PAT
surface may have no vault file id. Business outcomes never raise; only a
disabled integration does (PdmNotEnabledError).
"""

import re

from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.policies.made_item_rules import newest_of
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IMadeItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IPartNumberRegistryCadStore
from src.modules.catalogue.ports.outbound.catalogue_queries import IArticleGroupQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ICustomerQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISourceItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.external_data.application.dto.pdm_dto import PdmValidationResult
from src.modules.external_data.application.dto.pdm_dto import ValidatePdmPayloadCommand
from src.modules.external_data.application.services.pdm_field_resolution import find_other_kind_link
from src.modules.external_data.application.services.pdm_field_resolution import (
    resolve_article_group_ids,
)
from src.modules.external_data.application.services.pdm_field_resolution import resolve_existing_id
from src.modules.external_data.application.services.pdm_field_resolution import (
    resolve_file_identity_from_path,
)
from src.modules.external_data.application.services.pdm_field_resolution import resolve_manufacturer
from src.modules.external_data.application.services.pdm_integration import is_pdm_enabled
from src.modules.external_data.application.services.pdm_required_fields import (
    format_missing_required_fields_reason,
)
from src.modules.external_data.application.services.pdm_required_fields import is_revision_required
from src.modules.external_data.application.services.pdm_required_fields import (
    missing_required_fields,
)
from src.modules.external_data.application.services.pdm_required_fields import (
    split_missing_required_fields,
)
from src.modules.external_data.application.services.pdm_variables import kind_variable_name
from src.modules.external_data.application.services.pdm_variables import map_variables
from src.modules.external_data.application.services.pdm_variables import parse_edp_part_id
from src.modules.external_data.application.services.pdm_variables import parse_processes
from src.modules.external_data.application.services.pdm_variables import process_entry_missing_role
from src.modules.external_data.application.services.pdm_vault import file_extension
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.errors import PdmNotEnabledError
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)

_UNRESOLVED_IDENTITY_NOTE = "PDM file identity could not be resolved from the document path"

_VALID_KINDS = ("made", "bought")


class ValidatePdmPayload:
    def __init__(
        self,
        made_item_repo: IMadeItemCadStore,
        bought_item_repo: IBoughtItemCadStore,
        article_group_repo: IArticleGroupQueries,
        source_item_repo: ISourceItemQueries,
        supplier_repo: ISupplierQueries,
        admin_settings_repo: IExternalDataSettingsRepository,
        part_number_registry: IPartNumberRegistryCadStore,
        pdm_file_snapshot_repo: IPdmFileSnapshotRepository,
        customer_repo: ICustomerQueries,
    ) -> None:
        self._made_items = made_item_repo
        self._bought_items = bought_item_repo
        self._article_groups = article_group_repo
        self._source_items = source_item_repo
        self._suppliers = supplier_repo
        self._admin_settings = admin_settings_repo
        self._registry = part_number_registry
        self._snapshots = pdm_file_snapshot_repo
        self._customers = customer_repo

    async def execute(self, cmd: ValidatePdmPayloadCommand) -> PdmValidationResult:
        settings = await self._admin_settings.get_pdm()
        if not is_pdm_enabled(settings):
            raise PdmNotEnabledError(
                "The PDM integration is not enabled and configured; there is nothing to validate."
            )

        vault_id, file_id, file_identity = await self._resolve_identity(cmd, settings.vault_id)

        kind = self._resolve_kind(cmd, settings)
        if kind is None:
            return PdmValidationResult(
                ok=False,
                reasons=["kind not set"],
                pending_pdm=[],
                kind=None,
                part_number=None,
                revision=None,
                would="unknown",
                file_identity=file_identity,
                notes=[],
            )

        made_settings = await self._admin_settings.get_made_items()
        order_settings = await self._admin_settings.get_orders()
        variable_map = (
            settings.made_item_variable_map if kind == "made" else settings.bought_item_variable_map
        )
        mapped = map_variables(kind, variable_map, cmd.variables)

        part_number = (mapped.get("part_number") or "").strip()
        revision = (mapped.get("revision") or "").strip()

        pending_pdm = self._pending_pdm_fields(kind, part_number, revision, settings)
        reasons = await self._identity_reasons(
            kind, part_number, vault_id, file_id, made_settings, order_settings
        )
        reasons.extend(self._extension_reasons(cmd, kind, settings))

        notes: list[str] = []
        if kind == "made":
            would, extra_reasons = await self._would_made(part_number, revision, mapped)
        else:
            would, extra_reasons, extra_notes = await self._would_bought(
                part_number, mapped, vault_id, file_id, file_identity != "unresolved"
            )
            notes.extend(extra_notes)
        reasons.extend(extra_reasons)

        if would in ("created", "revised", "claimed", "unknown"):
            extra_required_reasons, pdm_missing = self._required_field_reasons(
                kind, mapped, settings
            )
            reasons.extend(extra_required_reasons)
            pending_pdm.extend(field for field in pdm_missing if field not in pending_pdm)

        return PdmValidationResult(
            ok=not reasons,
            reasons=reasons,
            pending_pdm=pending_pdm,
            kind=kind,
            part_number=part_number or None,
            revision=revision or None,
            would=would,
            file_identity=file_identity,
            notes=notes,
        )

    @staticmethod
    def _resolve_kind(cmd: ValidatePdmPayloadCommand, settings: AdminPdmSettings) -> str | None:
        kind = cmd.kind if cmd.kind in _VALID_KINDS else None
        if kind is None:
            raw = (cmd.variables.get(kind_variable_name(settings)) or "").strip()
            kind = raw if raw in _VALID_KINDS else None
        return kind

    @staticmethod
    def _pending_pdm_fields(
        kind: str, part_number: str, revision: str, settings: AdminPdmSettings
    ) -> list[str]:
        """Missing identity fields are pending rather than reasons, since the
        release workflow assigns them. A bought item's revision only counts
        when the admin requires it."""
        revision_required = is_revision_required(kind, settings)
        pending_pdm: list[str] = []
        if not part_number:
            pending_pdm.append("part_number")
        if revision_required and not revision:
            pending_pdm.append("revision")
        return pending_pdm

    async def _identity_reasons(
        self,
        kind: str,
        part_number: str,
        vault_id: str | None,
        file_id: int | None,
        made_settings: AdminMadeItemSettings,
        order_settings: AdminOrderSettings,
    ) -> list[str]:
        reasons: list[str] = []
        pattern_reason = self._pattern_reason(kind, part_number, made_settings, order_settings)
        if pattern_reason is not None:
            reasons.append(pattern_reason)
        reasons.extend(await self._link_reasons(kind, part_number, vault_id, file_id))
        return reasons

    @staticmethod
    def _pattern_reason(
        kind: str,
        part_number: str,
        made_settings: AdminMadeItemSettings,
        order_settings: AdminOrderSettings,
    ) -> str | None:
        if not part_number:
            return None
        pattern = (
            made_settings.pdm_part_number_pattern
            if kind == "made"
            else order_settings.pdm_part_number_pattern
        )
        if not pattern:
            return (
                f"no external PDM part number pattern configured for {kind} items "
                "(Numbering settings)"
            )
        if not re.fullmatch(pattern, part_number):
            return "part number does not match the configured PDM pattern"
        return None

    async def _link_reasons(
        self, kind: str, part_number: str, vault_id: str | None, file_id: int | None
    ) -> list[str]:
        reasons: list[str] = []
        if vault_id and file_id is not None:
            other = await find_other_kind_link(
                self._made_items, self._bought_items, vault_id, file_id, kind
            )
            if other is not None:
                other_kind = "bought" if kind == "made" else "made"
                reasons.append(f"kind changed, item already linked as {other_kind}")

        if part_number:
            owner = await self._registry.owner_of(part_number)
            if owner is not None and owner.kind != kind:
                reasons.append(f"part number is already registered to {owner.kind.value}")

        return reasons

    @staticmethod
    def _extension_reasons(
        cmd: ValidatePdmPayloadCommand, kind: str, settings: AdminPdmSettings
    ) -> list[str]:
        if not cmd.file_name:
            return []
        ext = file_extension(cmd.file_name)
        admitted = (
            settings.made_item_extensions if kind == "made" else settings.bought_item_extensions
        )
        if ext and ext not in admitted:
            return [f"{ext} files are not {kind} items"]
        return []

    @staticmethod
    def _required_field_reasons(
        kind: str, mapped: dict[str, str], settings: AdminPdmSettings
    ) -> tuple[list[str], list[str]]:
        """Required-field reasons and pending fields for an outcome other
        than `updated`, which ingest never checks either."""
        reasons: list[str] = []
        if kind == "made" and process_entry_missing_role(mapped.get("processes")):
            reasons.append("process entry without role")
        processes = parse_processes(mapped.get("processes")) if kind == "made" else []
        missing = missing_required_fields(kind, mapped, settings, processes)
        engineer_missing, pdm_missing = split_missing_required_fields(kind, missing)
        if engineer_missing:
            reasons.append(format_missing_required_fields_reason(engineer_missing))
        return reasons, pdm_missing

    async def _resolve_identity(
        self, cmd: ValidatePdmPayloadCommand, settings_vault_id: str
    ) -> tuple[str | None, int | None, str]:
        """(vault_id, file_id, file_identity). The API-key surface supplies
        the ids; the PAT surface may resolve them from `file_path`, and
        otherwise the checks needing a file id are left out."""
        if cmd.vault_id and cmd.file_id is not None:
            return cmd.vault_id, cmd.file_id, "not_applicable"
        if cmd.file_path:
            snapshot = await resolve_file_identity_from_path(
                self._snapshots, settings_vault_id, cmd.file_path
            )
            if snapshot is not None:
                return settings_vault_id, snapshot.file_id, "resolved"
        return None, None, "unresolved"

    async def _would_made(
        self, part_number: str, revision: str, mapped: dict[str, str]
    ) -> tuple[str, list[str]]:
        reasons: list[str] = []
        _, article_group_warning = await resolve_article_group_ids(mapped, self._article_groups)
        if article_group_warning:
            reasons.append(article_group_warning)
        # An empty reference means "no link", which is always allowed; only a value that is
        # present but points nowhere is a problem worth reporting. Whether the link is
        # required at all is the required-fields rule's business, checked separately.
        if mapped.get("bought_item_id", "").strip() and (
            await resolve_existing_id(mapped, "bought_item_id", self._bought_items.get_by_id)
            is None
        ):
            reasons.append(
                f"bought_item_id {mapped['bought_item_id']!r} does not resolve to an existing "
                "bought item"
            )
        if mapped.get("source_item_id", "").strip() and (
            await resolve_existing_id(mapped, "source_item_id", self._source_items.get_by_id)
            is None
        ):
            reasons.append(
                f"source_item_id {mapped['source_item_id']!r} does not resolve to an existing "
                "source item"
            )
        if mapped.get("customer_id", "").strip() and (
            await resolve_existing_id(mapped, "customer_id", self._customers.get_by_id) is None
        ):
            reasons.append(
                f"customer_id {mapped['customer_id']!r} does not resolve to an existing customer"
            )

        # A pending part number can only lead to a new row.
        if not part_number:
            return "created", reasons
        family = await self._made_items.get_revisions(part_number)
        if not family:
            return "created", reasons
        newest = newest_of(family)
        # A pending revision never equals the existing one, so it predicts
        # "revised", as the release workflow would.
        return ("updated" if revision == newest.revision else "revised"), reasons

    async def _would_bought(
        self,
        part_number: str,
        mapped: dict[str, str],
        vault_id: str | None,
        file_id: int | None,
        identity_known: bool,
    ) -> tuple[str, list[str], list[str]]:
        reasons: list[str] = []
        notes: list[str] = []
        manufacturer_id, manufacturer_unresolved = await resolve_manufacturer(
            mapped, self._suppliers
        )
        _, article_group_warning = await resolve_article_group_ids(mapped, self._article_groups)
        if article_group_warning:
            reasons.append(article_group_warning)
        # Checked for its form only: ingest never asks the portal, so neither does the dry run.
        edp_raw = mapped.get("edp_part_id", "").strip()
        if edp_raw and parse_edp_part_id(edp_raw) is None:
            reasons.append(f"edp_part_id {edp_raw!r} is not an EPLAN Data Portal part id")

        # A pending part number can never match an existing row.
        existing = await self._bought_items.get_by_part_number(part_number) if part_number else None
        if existing is not None:
            if manufacturer_unresolved:
                reasons.append("manufacturer unresolved")
            if existing.pdm_file_id is None:
                # An unlinked row with this part number would be claimed.
                return "claimed", reasons, notes
            if not identity_known:
                # Without a file identity, assume this is the linked file.
                notes.append(_UNRESOLVED_IDENTITY_NOTE)
                return "updated", reasons, notes
            if existing.vault_id == vault_id and existing.pdm_file_id == file_id:
                return "updated", reasons, notes
            reasons.append(f"part number linked to another PDM file (id {existing.pdm_file_id})")
            return "unknown", reasons, notes

        # Required to create or claim a row.
        if manufacturer_id is None:
            reasons.append("manufacturer unresolved")

        candidate = await self._bought_items.find_claim_candidate(
            gtin=mapped.get("gtin") or None,
            manufacturer_id=manufacturer_id,
            order_code_1=mapped.get("order_code_1") or None,
        )
        return ("claimed" if candidate is not None else "created"), reasons, notes
