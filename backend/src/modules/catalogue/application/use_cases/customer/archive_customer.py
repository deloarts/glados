"""
Idempotent: archiving an already-archived customer is not an error.
"""

from src.modules.catalogue.application.dto.customer_dto import CustomerResult
from src.modules.catalogue.application.mappers.customer_mapper import CustomerMapper
from src.modules.catalogue.domain.errors import CustomerNotFoundError
from src.modules.catalogue.domain.services.customer_rules import CustomerRules
from src.modules.catalogue.ports.outbound.repositories.customer_repository import (
    ICustomerRepository,
)
from src.modules.platform.application.services.archive_restore import set_archived
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class ArchiveCustomer:
    def __init__(
        self,
        customer_repo: ICustomerRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._customers = customer_repo
        self._uow = uow

    async def execute(self, actor: User, customer_id: int) -> CustomerResult:
        CustomerRules.assert_can_archive(actor)

        saved = await set_archived(
            entity_id=customer_id,
            archived=True,
            load=self._customers.get_by_id,
            not_found=lambda cid: CustomerNotFoundError(f"Customer #{cid} not found."),
            save=self._customers.save,
        )
        await self._uow.commit()

        log.info(f"Archived customer {saved.name!r} (ID={saved.id}).")

        return CustomerMapper.to_result(saved)
