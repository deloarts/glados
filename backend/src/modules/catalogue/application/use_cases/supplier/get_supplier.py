"""Use cases for retrieving supplier information by ID or with pagination and filtering."""

from src.modules.catalogue.application.dto.supplier_dto import SupplierResult
from src.modules.catalogue.application.mappers.supplier_mapper import SupplierMapper
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.ports.outbound.catalogue_queries import SupplierFilterDto
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise


class PaginatedSuppliers:
    def __init__(self, total: int, items: list[SupplierResult]):
        self.total = total
        self.items = items


class GetSupplier:
    def __init__(self, supplier_repo: ISupplierRepository) -> None:
        self._suppliers = supplier_repo

    async def execute(self, supplier_id: int) -> SupplierResult:
        return SupplierMapper.to_result(await self._read(supplier_id))

    async def changelog(self, supplier_id: int) -> list[str]:
        """The supplier's changelog lines; a missing id raises
        SupplierNotFoundError, as execute does."""
        return (await self._read(supplier_id)).changes

    async def _read(self, supplier_id: int) -> Supplier:
        return found_or_raise(
            await self._suppliers.get_by_id(supplier_id),
            SupplierNotFoundError,
            f"Supplier #{supplier_id} not found.",
        )


class GetSuppliers:
    def __init__(self, supplier_repo: ISupplierRepository) -> None:
        self._suppliers = supplier_repo

    async def execute(self, filters: SupplierFilterDto) -> PaginatedSuppliers:
        total, items = await self._suppliers.get_multi(filters)
        return PaginatedSuppliers(total=total, items=[SupplierMapper.to_result(i) for i in items])
