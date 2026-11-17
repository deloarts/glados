"""
Deletes a made item demand through the delete the demand families share
(_demand_family/delete_demand.py). A demand that still holds allocations is
refused and is canceled instead.
"""

from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemDemandItemResult
from src.modules.fulfillment.application.use_cases._demand_family.delete_demand import DeleteDemand
from src.modules.fulfillment.application.use_cases.made_item_demand._spec import SPEC
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem


class DeleteDemandItem(DeleteDemand[MadeItemDemandItem, MadeItemDemandItemResult]):
    _spec = SPEC
