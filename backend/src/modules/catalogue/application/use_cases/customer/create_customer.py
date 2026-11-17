"""
Creates a new customer record. Rejects a VAT ID that already belongs to
another customer, since VAT ID is the practical dedup key across otherwise
similar customer names.
"""

from src.modules.catalogue.application.dto.customer_dto import CreateCustomerCommand
from src.modules.catalogue.application.dto.customer_dto import CustomerResult
from src.modules.catalogue.application.mappers.customer_mapper import CustomerMapper
from src.modules.catalogue.domain.entities.customer import Customer
from src.modules.catalogue.domain.errors import CustomerAlreadyExistsError
from src.modules.catalogue.domain.services.customer_rules import CustomerRules
from src.modules.catalogue.domain.value_objects.customer_level import CustomerLevel
from src.modules.catalogue.ports.outbound.repositories.customer_repository import (
    ICustomerRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class CreateCustomer:
    def __init__(
        self,
        customer_repo: ICustomerRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._customers = customer_repo
        self._uow = uow

    async def execute(self, actor: User, cmd: CreateCustomerCommand) -> CustomerResult:
        CustomerRules.assert_can_create(actor)

        if cmd.vat_id and await self._customers.get_by_vat_id(cmd.vat_id):
            raise CustomerAlreadyExistsError(
                f"A customer with VAT ID {cmd.vat_id!r} already exists."
            )

        customer = Customer(
            id=0,
            created=now_utc(),
            changed=None,
            changes=[],
            archived=False,
            name=cmd.name,
            legal_name=cmd.legal_name,
            vat_id=cmd.vat_id,
            level=CustomerLevel(cmd.level),
            street=cmd.street,
            city=cmd.city,
            country=cmd.country,
            postal_code=cmd.postal_code,
            email=cmd.email,
            phone=cmd.phone,
            weblink=cmd.weblink,
            creator_id=actor.id,
        )
        saved = await self._customers.save(customer)
        await self._uow.commit()

        log.info(f"Created customer {saved.name!r} (ID={saved.id}).")

        return CustomerMapper.to_result(saved)
