"""
Edits a bought item demand through the edit the demand families share
(_demand_family/update_demand.py). A bought item demand adds no field of
its own.
"""

from src.modules.fulfillment.application.dto.bought_item_demand_dto import DemandItemResult
from src.modules.fulfillment.application.dto.bought_item_demand_dto import UpdateDemandItemCommand
from src.modules.fulfillment.application.use_cases._demand_family.update_demand import UpdateDemand
from src.modules.fulfillment.application.use_cases.bought_item_demand._demand_spec import SPEC
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.services.bought_item_demand_rules import BoughtItemDemandRules


class UpdateDemandItem(
    UpdateDemand[BoughtItemDemandItem, UpdateDemandItemCommand, DemandItemResult]
):
    _spec = SPEC
    _demand_rules = BoughtItemDemandRules
