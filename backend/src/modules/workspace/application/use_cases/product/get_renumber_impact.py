"""
What changing a product's number would affect, for the confirmation the
product dialog shows before saving a new number. The product number is
stored once and read live everywhere else, so only three things are
affected: the names of the product's devices (whose ASCII form CAD files
use), released calculations and checklists of the product and its projects
together with their exported reports (both show the old number), and
external systems that look the product up by number, which the dialog
always mentions since Glados cannot know them. Nothing is written.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.workspace.application.dto.product_dto import ProductRenumberExample
from src.modules.workspace.application.dto.product_dto import ProductRenumberImpactResult
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.policies.product_device_naming import DeviceName
from src.modules.workspace.domain.policies.product_device_naming import with_product_number
from src.modules.workspace.ports.outbound.product_documents_port import IProductDocuments
from src.modules.workspace.ports.outbound.repositories.product_device_repository import (
    IProductDeviceRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository

EXAMPLE_COUNT = 3
# Lineages read for the export count; a product with more documents than
# this is counted on the first ones, which is enough for a warning.
LINEAGE_LIMIT = 500


class GetProductRenumberImpact:
    def __init__(
        self,
        product_repo: IProductRepository,
        device_repo: IProductDeviceRepository,
        documents: IProductDocuments,
    ) -> None:
        self._products = product_repo
        self._devices = device_repo
        self._documents = documents

    async def execute(self, product_id: int, new_number: str) -> ProductRenumberImpactResult:
        product = found_or_raise(
            await self._products.get_by_id(product_id),
            ProductNotFoundError,
            f"Product #{product_id} not found.",
        )
        new_number = new_number.strip()

        devices = await self._devices.get_by_product(product.id, include_archived=False)
        examples = [
            ProductRenumberExample(
                old_name=with_product_number(
                    product.product_number, DeviceName(d.name_utf8, d.name_ascii)
                ).ascii,
                new_name=with_product_number(
                    new_number, DeviceName(d.name_utf8, d.name_ascii)
                ).ascii,
            )
            for d in devices[:EXAMPLE_COUNT]
        ]

        counts = await self._documents.renumber_counts(product.id)
        return ProductRenumberImpactResult(
            device_count=len(devices),
            device_examples=examples,
            released_document_count=counts.released,
            export_count=counts.exports,
        )
