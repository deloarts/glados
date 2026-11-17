"""
Retrieves one customer by ID, or lists customers with filtering and
pagination.
"""

from src.modules.catalogue.application.dto.customer_dto import CustomerResult
from src.modules.catalogue.application.mappers.customer_mapper import CustomerMapper
from src.modules.catalogue.domain.errors import CustomerNotFoundError
from src.modules.catalogue.ports.outbound.repositories.customer_repository import CustomerFilterDto
from src.modules.catalogue.ports.outbound.repositories.customer_repository import (
    ICustomerRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise


class PaginatedCustomers:
    def __init__(self, total: int, items: list[CustomerResult]):
        self.total = total
        self.items = items


class GetCustomer:
    def __init__(self, customer_repo: ICustomerRepository) -> None:
        self._repo = customer_repo

    async def execute(self, customer_id: int) -> CustomerResult:
        customer = found_or_raise(
            await self._repo.get_by_id(customer_id),
            CustomerNotFoundError,
            f"Customer #{customer_id} not found.",
        )
        return CustomerMapper.to_result(customer)


class GetCustomers:
    def __init__(self, customer_repo: ICustomerRepository) -> None:
        self._repo = customer_repo

    async def execute(self, filters: CustomerFilterDto) -> PaginatedCustomers:
        total, customers = await self._repo.get_multi(filters)
        return PaginatedCustomers(
            total=total,
            items=[CustomerMapper.to_result(c) for c in customers],
        )
