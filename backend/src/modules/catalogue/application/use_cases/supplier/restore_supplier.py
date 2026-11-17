"""
Restores an archived supplier. Raises SupplierAlreadyExistsError (409) if
another live supplier already holds this one's VAT id (the live-row
uniqueness `uq_supplier_vat_id_active` would otherwise be violated).
Idempotent: restoring an already-live supplier is not an error.
"""

from src.modules.catalogue.application.dto.supplier_dto import SupplierResult
from src.modules.catalogue.application.mappers.supplier_mapper import SupplierMapper
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.errors import SupplierAlreadyExistsError
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.domain.services.supplier_rules import SupplierRules
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.application.services.archive_restore import set_archived
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class RestoreSupplier:
    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._suppliers = supplier_repo
        self._uow = uow

    async def execute(self, actor: User, supplier_id: int) -> SupplierResult:
        SupplierRules.assert_can_restore(actor)

        async def _before_save(supplier: Supplier) -> None:
            if supplier.archived and supplier.vat_id:
                conflict = await self._suppliers.get_by_vat_id(supplier.vat_id)
                if conflict and conflict.id != supplier.id:
                    raise SupplierAlreadyExistsError(
                        f"A supplier with VAT ID {supplier.vat_id!r} already exists."
                    )

            supplier.changed = now_utc()
            supplier.changes = append_changelog(
                supplier.changes, actor.full_name, "Supplier restored."
            )

        saved = await set_archived(
            entity_id=supplier_id,
            archived=False,
            load=self._suppliers.get_by_id,
            not_found=lambda sid: SupplierNotFoundError(f"Supplier #{sid} not found."),
            save=self._suppliers.save,
            before_save=_before_save,
        )
        await self._uow.commit()
        log.info(f"Restored supplier {saved.name!r}, ID={saved.id}.")
        return SupplierMapper.to_result(saved)
