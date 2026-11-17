"""
The words and errors one demand family reports with, so a rule or use case
the bought, made and source item demands share still names the demand the
way its family does. Bought and made demands share their noun, "Demand
item", and their errors; source item demands have their own. The terminal
statuses come from each family's status enum, although the three families
store the same values. No I/O.
"""

from dataclasses import dataclass

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.errors import DemandItemAlreadyCanceledError
from src.modules.fulfillment.domain.errors import DemandItemAlreadyFulfilledError
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.domain.errors import SourceItemDemandAlreadyCanceledError
from src.modules.fulfillment.domain.errors import SourceItemDemandAlreadyFulfilledError
from src.modules.fulfillment.domain.errors import SourceItemDemandNotFoundError
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.exceptions import DomainError


@dataclass(frozen=True)
class DemandTerms:
    """One family's terms. `noun` starts a message, as in "Demand item #12
    is already fulfilled."; `fulfilled` and `canceled` are the stored values
    of the two terminal statuses."""

    noun: str
    fulfilled: str
    canceled: str
    not_found_error: type[DomainError]
    already_fulfilled_error: type[DomainError]
    already_canceled_error: type[DomainError]


BOUGHT_DEMAND_TERMS = DemandTerms(
    noun="Demand item",
    fulfilled=BoughtItemDemandStatus.FULFILLED,
    canceled=BoughtItemDemandStatus.CANCELED,
    not_found_error=DemandItemNotFoundError,
    already_fulfilled_error=DemandItemAlreadyFulfilledError,
    already_canceled_error=DemandItemAlreadyCanceledError,
)

MADE_DEMAND_TERMS = DemandTerms(
    noun="Demand item",
    fulfilled=MadeItemDemandStatus.FULFILLED,
    canceled=MadeItemDemandStatus.CANCELED,
    not_found_error=DemandItemNotFoundError,
    already_fulfilled_error=DemandItemAlreadyFulfilledError,
    already_canceled_error=DemandItemAlreadyCanceledError,
)

SOURCE_DEMAND_TERMS = DemandTerms(
    noun="Source item demand",
    fulfilled=SourceItemDemandStatus.FULFILLED,
    canceled=SourceItemDemandStatus.CANCELED,
    not_found_error=SourceItemDemandNotFoundError,
    already_fulfilled_error=SourceItemDemandAlreadyFulfilledError,
    already_canceled_error=SourceItemDemandAlreadyCanceledError,
)
