"""Use case for updating supplier information with change tracking and audit logging."""

from src.modules.catalogue.application.dto.supplier_dto import SupplierResult
from src.modules.catalogue.application.dto.supplier_dto import UpdateSupplierCommand
from src.modules.catalogue.application.mappers.supplier_mapper import SupplierMapper
from src.modules.catalogue.domain.errors import SupplierAlreadyExistsError
from src.modules.catalogue.domain.errors import SupplierEdpCodeInUseError
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.domain.services.supplier_edp_code import normalize_edp_code
from src.modules.catalogue.domain.services.supplier_rules import SupplierRules
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.application.services.command_changelog import diff_command
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class UpdateSupplier:
    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        *,
        uow: IUnitOfWork,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._suppliers = supplier_repo
        self._uow = uow
        self._recompute = recompute_schedule

    async def execute(
        self, actor: User, supplier_id: int, cmd: UpdateSupplierCommand
    ) -> SupplierResult:
        SupplierRules.assert_can_update(actor)

        await self._suppliers.lock_for_update(supplier_id)
        supplier = found_or_raise(
            await self._suppliers.get_by_id(supplier_id),
            SupplierNotFoundError,
            f"Supplier #{supplier_id} not found.",
        )
        assert_edit_version(supplier, cmd.expected_edit_version, what=f"Supplier #{supplier.id}")

        if cmd.vat_id and cmd.vat_id != supplier.vat_id:
            existing = await self._suppliers.get_by_vat_id(cmd.vat_id)
            if existing and existing.id != supplier.id:
                raise SupplierAlreadyExistsError(
                    f"A supplier with VAT ID {cmd.vat_id!r} already exists."
                )

        cmd = cmd.model_copy(update={"edp_code": normalize_edp_code(cmd.edp_code)})
        if cmd.edp_code and cmd.edp_code != supplier.edp_code:
            holder = await self._suppliers.get_by_edp_code(cmd.edp_code)
            if holder and holder.id != supplier.id:
                raise SupplierEdpCodeInUseError(
                    f"Another supplier already has the Data Portal code {cmd.edp_code!r}."
                )
        changelog_entry = diff_command(supplier, cmd)

        supplier.name = cmd.name
        supplier.legal_name = cmd.legal_name
        supplier.vat_id = cmd.vat_id
        supplier.level = SupplierLevel(cmd.level)
        supplier.external_lead_time_days = cmd.external_lead_time_days
        supplier.edp_code = cmd.edp_code
        supplier.edp_type_number_first = cmd.edp_type_number_first
        supplier.capability_ids = cmd.capability_ids
        supplier.article_group_ids = cmd.article_group_ids
        supplier.street = cmd.street
        supplier.city = cmd.city
        supplier.country = cmd.country
        supplier.postal_code = cmd.postal_code
        supplier.email = cmd.email
        supplier.phone = cmd.phone
        supplier.weblink = cmd.weblink
        supplier.order_email = cmd.order_email
        supplier.order_language = cmd.order_language
        supplier.order_template = cmd.order_template
        supplier.request_email = cmd.request_email
        supplier.request_language = cmd.request_language
        supplier.request_template = cmd.request_template
        supplier.changed = now_utc()
        supplier.changes = append_changelog(supplier.changes, actor.full_name, changelog_entry)

        saved = await self._suppliers.save(supplier)
        await self._uow.commit()
        # Its lead time dates the external steps that use it.
        await recompute_schedule_after_commit(
            self._recompute, after="changing a supplier; the change itself is committed."
        )
        log.info(f"Updated supplier {saved.name!r}, ID={saved.id}.")
        return SupplierMapper.to_result(saved)
