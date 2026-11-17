"""
Updates an existing customer's details. Rejects a VAT ID change that would
collide with another live customer's VAT ID.
"""

from src.modules.catalogue.application.dto.customer_dto import CustomerResult
from src.modules.catalogue.application.dto.customer_dto import UpdateCustomerCommand
from src.modules.catalogue.application.mappers.customer_mapper import CustomerMapper
from src.modules.catalogue.domain.errors import CustomerAlreadyExistsError
from src.modules.catalogue.domain.errors import CustomerNotFoundError
from src.modules.catalogue.domain.services.customer_rules import CustomerRules
from src.modules.catalogue.domain.value_objects.customer_level import CustomerLevel
from src.modules.catalogue.ports.outbound.repositories.customer_repository import (
    ICustomerRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class UpdateCustomer:
    def __init__(
        self,
        customer_repo: ICustomerRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._customers = customer_repo
        self._uow = uow

    async def execute(
        self, actor: User, customer_id: int, cmd: UpdateCustomerCommand
    ) -> CustomerResult:
        CustomerRules.assert_can_update(actor)

        await self._customers.lock_for_update(customer_id)
        customer = found_or_raise(
            await self._customers.get_by_id(customer_id),
            CustomerNotFoundError,
            f"Customer #{customer_id} not found.",
        )
        assert_edit_version(customer, cmd.expected_edit_version, what=f"Customer #{customer.id}")

        if cmd.vat_id and cmd.vat_id != customer.vat_id:
            existing = await self._customers.get_by_vat_id(cmd.vat_id)
            if existing and existing.id != customer.id:
                raise CustomerAlreadyExistsError(
                    f"A customer with VAT ID {cmd.vat_id!r} already exists."
                )

        customer.name = cmd.name
        customer.legal_name = cmd.legal_name
        customer.vat_id = cmd.vat_id
        customer.level = CustomerLevel(cmd.level)
        customer.street = cmd.street
        customer.city = cmd.city
        customer.country = cmd.country
        customer.postal_code = cmd.postal_code
        customer.email = cmd.email
        customer.phone = cmd.phone
        customer.weblink = cmd.weblink
        customer.changed = now_utc()

        saved = await self._customers.save(customer)
        await self._uow.commit()

        log.info(f"Updated customer {saved.name!r} (ID={saved.id}).")

        return CustomerMapper.to_result(saved)
