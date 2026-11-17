"""
The lifecycle tables of Planning & fulfillment as the reconciler and the use
cases run them: the derivation table of each derived status, the intent table
of each aggregate, and the status changes observed in the lifecycle model.
Readers outside this module, such as the state machine catalogue of the
handbook, describe the lifecycles from these objects and never change them.
"""

from src.modules.fulfillment.domain.services.lifecycle.demand import BOUGHT_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.demand import MADE_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.demand import SOURCE_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.intents import DEMAND_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import LOT_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import LOT_POSITION_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_ITEM_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import PRODUCTION_ORDER_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.lot import LOT_STATUS
from src.modules.fulfillment.domain.services.lifecycle.lot_position import POSITION_KIND
from src.modules.fulfillment.domain.services.lifecycle.lot_position import POSITION_STATUS
from src.modules.fulfillment.domain.services.lifecycle.observed_transitions import TRANSITIONS
from src.modules.fulfillment.domain.services.lifecycle.order import ORDER_STATUS
from src.modules.fulfillment.domain.services.lifecycle.order_item import ORDER_ITEM_STATUS
from src.modules.fulfillment.domain.services.lifecycle.production_order import (
    PRODUCTION_ORDER_STATUS,
)
from src.modules.fulfillment.domain.services.lifecycle.quote_request import QUOTE_REQUEST_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.quote_request import QUOTE_REQUEST_STATUS
from src.modules.fulfillment.domain.services.lifecycle.rules import DerivationTable

__all__ = [
    "BOUGHT_DEMAND_STATUS",
    "DEMAND_INTENTS",
    "LOT_INTENTS",
    "LOT_POSITION_INTENTS",
    "LOT_STATUS",
    "MADE_DEMAND_STATUS",
    "ORDER_INTENTS",
    "ORDER_ITEM_INTENTS",
    "ORDER_ITEM_STATUS",
    "ORDER_STATUS",
    "POSITION_KIND",
    "POSITION_STATUS",
    "PRODUCTION_ORDER_INTENTS",
    "PRODUCTION_ORDER_STATUS",
    "QUOTE_REQUEST_INTENTS",
    "QUOTE_REQUEST_STATUS",
    "SOURCE_DEMAND_STATUS",
    "TRANSITIONS",
    "DerivationTable",
]
