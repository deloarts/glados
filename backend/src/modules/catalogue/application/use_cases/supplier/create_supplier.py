"""
Creates a new supplier with full contact, address, and ordering
template metadata.
"""

from src.modules.catalogue.application.dto.supplier_dto import CreateSupplierCommand
from src.modules.catalogue.application.dto.supplier_dto import SupplierResult
from src.modules.catalogue.application.mappers.supplier_mapper import SupplierMapper
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.errors import SupplierAlreadyExistsError
from src.modules.catalogue.domain.errors import SupplierEdpCodeInUseError
from src.modules.catalogue.domain.services.supplier_edp_code import normalize_edp_code
from src.modules.catalogue.domain.services.supplier_rules import SupplierRules
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CreateSupplier:
    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._suppliers = supplier_repo
        self._uow = uow

    async def execute(self, actor: User, cmd: CreateSupplierCommand) -> SupplierResult:
        SupplierRules.assert_can_create(actor)

        edp_code = normalize_edp_code(cmd.edp_code)
        if edp_code and await self._suppliers.get_by_edp_code(edp_code):
            raise SupplierEdpCodeInUseError(
                f"Another supplier already has the Data Portal code {edp_code!r}."
            )

        if cmd.vat_id and await self._suppliers.get_by_vat_id(cmd.vat_id):
            raise SupplierAlreadyExistsError(
                f"A supplier with VAT ID {cmd.vat_id!r} already exists."
            )

        now = now_utc()
        supplier = Supplier(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Supplier created."),
            archived=False,
            name=cmd.name,
            legal_name=cmd.legal_name,
            vat_id=cmd.vat_id,
            level=SupplierLevel(cmd.level) if cmd.level else SupplierLevel.default(),
            external_lead_time_days=cmd.external_lead_time_days,
            edp_code=edp_code,
            edp_type_number_first=cmd.edp_type_number_first,
            capability_ids=cmd.capability_ids,
            article_group_ids=cmd.article_group_ids,
            street=cmd.street,
            city=cmd.city,
            country=cmd.country,
            postal_code=cmd.postal_code,
            email=cmd.email,
            phone=cmd.phone,
            weblink=cmd.weblink,
            order_email=cmd.order_email,
            order_language=cmd.order_language,
            order_template=cmd.order_template,
            request_email=cmd.request_email,
            request_language=cmd.request_language,
            request_template=cmd.request_template,
            creator_id=actor.id,
            creator=actor,
        )

        saved = await self._suppliers.save(supplier)
        await self._uow.commit()
        log.info(f"Created supplier {saved.name!r}, ID={saved.id}.")
        return SupplierMapper.to_result(saved)
