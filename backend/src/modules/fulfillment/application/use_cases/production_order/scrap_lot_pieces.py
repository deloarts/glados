"""
Resolves a lot's own scrap request (POST /production-lots/{id}/scrap,
opened from the lot detail controls bar or the lots table context menu)
to a production order id and delegates the whole disposition to
ScrapProductionPieces, so the order-first and lot-first entry points
share exactly one implementation. production_order_id is optional on the
command: when the targeted position has exactly one open (non-terminal)
production order, it's the obvious target and doesn't need to be named
explicitly; with several, the caller must disambiguate. A named order must
belong to the position, so a request cannot scrap another lot's pieces. A
lot that has ended, or a position with no open order, is refused with the
reason, since there is no work left to scrap pieces from.
"""

from src.modules.fulfillment.application.dto.production_lot_dto import ScrapLotPiecesCommand
from src.modules.fulfillment.application.dto.production_lot_dto import ScrapPiecesResult
from src.modules.fulfillment.application.dto.production_order_dto import (
    ScrapProductionPiecesCommand,
)
from src.modules.fulfillment.application.use_cases.production_order.scrap_production_pieces import (
    ScrapProductionPieces,
)
from src.modules.fulfillment.domain.errors import LotNotScrappableError
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderSelectionRequiredError
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.domain.entities.user import User


class ScrapLotPieces:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        order_repo: IProductionOrderRepository,
        scrap_production_pieces: ScrapProductionPieces,
    ) -> None:
        self._lots = lot_repo
        self._orders = order_repo
        self._scrap = scrap_production_pieces

    async def execute(
        self, actor: User, lot_id: int, cmd: ScrapLotPiecesCommand
    ) -> ScrapPiecesResult:
        position = await self._lots.get_position_by_id(cmd.position_id)
        if not position or position.lot_id != lot_id:
            raise LotPositionNotFoundError(
                f"Position #{cmd.position_id} not found on lot #{lot_id}."
            )

        if cmd.production_order_id is not None:
            await self._assert_order_on_position(cmd.production_order_id, position.id, lot_id)
            production_order_id = cmd.production_order_id
        else:
            production_order_id = await self._resolve_single_open_order(lot_id, position.id)

        return await self._scrap.execute(
            actor,
            ScrapProductionPiecesCommand(
                production_order_id=production_order_id,
                quantity=cmd.quantity,
                reason=cmd.reason,
                note=cmd.note,
                create_replacement=cmd.create_replacement,
                operator_id=cmd.operator_id,
                expected_lot_edit_version=cmd.expected_edit_version,
            ),
        )

    async def _assert_order_on_position(self, order_id: int, position_id: int, lot_id: int) -> None:
        order = await self._orders.get_by_id(order_id)
        if order is None or order.lot_position_id != position_id:
            raise ProductionOrderNotFoundError(
                f"Production order #{order_id} is not on position #{position_id} of lot #{lot_id}."
            )

    async def _resolve_single_open_order(self, lot_id: int, position_id: int) -> int:
        open_orders = [
            o
            for o in await self._orders.get_by_lot_position_id(position_id)
            if o.status not in TERMINAL_PRODUCTION_ORDER_STATUSES
        ]
        if len(open_orders) == 1:
            return open_orders[0].id
        if not open_orders:
            lot = await self._lots.get_by_id(lot_id)
            if lot is not None and lot.status in TERMINAL_LOT_STATUSES:
                raise LotNotScrappableError(
                    f"Lot #{lot_id} is {lot.status.value}; there is no work left to scrap pieces from."
                )
            raise LotNotScrappableError(
                f"Position #{position_id} has no open production order; pieces are scrapped "
                "from the order that works on them."
            )
        raise ProductionOrderSelectionRequiredError(
            f"Position #{position_id} has {len(open_orders)} open production orders; name the "
            "one the pieces were scrapped on."
        )
