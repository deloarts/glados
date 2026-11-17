"""
Deletes a bought item demand through the delete the demand families share
(_demand_family/delete_demand.py). A demand that still holds allocations is
refused and is canceled instead.
"""

from src.modules.fulfillment.application.dto.bought_item_demand_dto import DemandItemResult
from src.modules.fulfillment.application.use_cases._demand_family.delete_demand import DeleteDemand
from src.modules.fulfillment.application.use_cases.bought_item_demand._demand_spec import SPEC
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem


class DeleteDemandItem(DeleteDemand[BoughtItemDemandItem, DemandItemResult]):
    _spec = SPEC
