"""
The rules of the demand items of bought items.
"""

from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.errors import DemandItemInvalidQuantityError
from src.modules.fulfillment.domain.services.demand_ownership_rules import assert_can_update_demand
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission


class BoughtItemDemandRules:
    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_DEMAND_ITEMS, "create", "demand items")

    @staticmethod
    def assert_can_update(actor: User, demand: BoughtItemDemandItem) -> None:
        assert_can_update_demand(actor, demand)

    @staticmethod
    def assert_valid_quantity(quantity: float) -> None:
        if quantity <= 0:
            raise DemandItemInvalidQuantityError(
                f"Quantity must be greater than zero (got {quantity})."
            )
