"""Use cases for retrieving products by ID, number, or designated user."""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.workspace.application.dto.product_dto import ProductResult
from src.modules.workspace.application.mappers.product_mapper import ProductMapper
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.modules.workspace.ports.outbound.repositories.product_repository import ProductFilterDto


class PaginatedProducts:
    def __init__(self, total: int, items: list[ProductResult]):
        self.total = total
        self.items = items


class GetProduct:
    def __init__(self, product_repo: IProductRepository) -> None:
        self._repo = product_repo

    async def execute(self, product_id: int) -> ProductResult:
        product = found_or_raise(
            await self._repo.get_by_id(product_id),
            ProductNotFoundError,
            f"Product #{product_id} not found.",
        )
        return ProductMapper.to_result(product)


class GetProductByNumber:
    def __init__(self, product_repo: IProductRepository) -> None:
        self._repo = product_repo

    async def execute(self, product_number: str) -> ProductResult:
        product = found_or_raise(
            await self._repo.get_by_product_number(product_number),
            ProductNotFoundError,
            f"Product with number {product_number!r} not found.",
        )
        return ProductMapper.to_result(product)


class GetMyProducts:
    def __init__(self, product_repo: IProductRepository) -> None:
        self._repo = product_repo

    async def execute(self, user_id: int) -> list[ProductResult]:
        products = await self._repo.get_by_designated_user_id(user_id)
        return [ProductMapper.to_result(p) for p in products]


class GetProducts:
    def __init__(self, product_repo: IProductRepository) -> None:
        self._repo = product_repo

    async def execute(self, filters: ProductFilterDto) -> PaginatedProducts:
        total, products = await self._repo.get_multi(filters)
        return PaginatedProducts(
            total=total,
            items=[ProductMapper.to_result(p) for p in products],
        )
