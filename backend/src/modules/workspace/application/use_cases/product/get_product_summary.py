"""
Read-side use case for a product's order cost and demand-status rollup over
all projects built on it, shown on the product detail page.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.ports.outbound.project_work_port import IProductWork
from src.modules.workspace.ports.outbound.project_work_port import ProjectSummaryRow
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository


class GetProductSummary:
    def __init__(self, product_repo: IProductRepository, order_repo: IProductWork) -> None:
        self._products = product_repo
        self._orders = order_repo

    async def execute(self, product_id: int) -> ProjectSummaryRow:
        found_or_raise(
            await self._products.get_by_id(product_id),
            ProductNotFoundError,
            f"Product #{product_id} not found.",
        )
        return await self._orders.get_product_summary(product_id)
