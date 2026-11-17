"""
Loads what a sequence's content may refer to (see SequenceContext): the
product's devices, their kinds and the product's variants, archived ones
included so a draft's kept references still resolve.
"""

from src.modules.quality.domain.services.sequence_rules import SequenceContext
from src.modules.quality.domain.services.sequence_rules import SequenceReferences
from src.modules.workspace.ports.outbound.workspace_queries import IProductDeviceKindQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProductDeviceQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProductVariantQueries


class SequenceContextLoader:
    def __init__(
        self,
        device_repo: IProductDeviceQueries,
        kind_repo: IProductDeviceKindQueries,
        variant_repo: IProductVariantQueries,
    ) -> None:
        self._devices = device_repo
        self._kinds = kind_repo
        self._variants = variant_repo

    async def load(
        self, product_id: int, kept: SequenceReferences | None = None
    ) -> SequenceContext:
        devices = await self._devices.get_by_product(product_id, include_archived=True)
        kinds = await self._kinds.get_many(include_archived=True)
        variants = await self._variants.get_by_product(product_id, include_archived=True)
        return SequenceContext(
            devices={device.id: device for device in devices},
            kinds={kind.id: kind for kind in kinds},
            variants={variant.id: variant for variant in variants},
            kept=kept or SequenceReferences(),
        )
