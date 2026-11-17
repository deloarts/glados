"""
Business rules for the made-item demand + allocation aggregates. No I/O.
No ORM. Mirrors BoughtItemDemandRules / BoughtItemAllocationRules
(bought_item_rules.py, allocation_service.py), minus substitution support
(made items aren't substitutable the way bought items are).
"""

from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.errors import DemandItemInvalidAlterationError
from src.modules.fulfillment.domain.errors import DemandItemInvalidQuantityError
from src.modules.fulfillment.domain.services.allocation_coverage import DemandAllocationRules
from src.modules.fulfillment.domain.services.demand_ownership_rules import assert_can_update_demand
from src.modules.fulfillment.domain.services.demand_terms import MADE_DEMAND_TERMS
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission

# ── Demand item rules ─────────────────────────────────────────────────


class MadeItemDemandRules:
    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_DEMAND_ITEMS, "create", "demand items")

    @staticmethod
    def assert_can_update(actor: User, demand: MadeItemDemandItem) -> None:
        assert_can_update_demand(actor, demand)

    @staticmethod
    def assert_valid_quantity(quantity: float) -> None:
        if quantity <= 0:
            raise DemandItemInvalidQuantityError(
                f"Quantity must be greater than zero (got {quantity})."
            )

    @staticmethod
    def assert_valid_alteration(
        made_item_id: int, is_alteration: bool, alteration_of_made_item_id: int | None
    ) -> None:
        if is_alteration:
            if alteration_of_made_item_id is None:
                raise DemandItemInvalidAlterationError(
                    "alteration_of_made_item_id is required when is_alteration is set."
                )
            if alteration_of_made_item_id == made_item_id:
                raise DemandItemInvalidAlterationError(
                    "A demand cannot be an alteration of the same made item it demands."
                )
        elif alteration_of_made_item_id is not None:
            raise DemandItemInvalidAlterationError(
                "alteration_of_made_item_id must be empty when is_alteration is not set."
            )


# ── Allocation rules ──────────────────────────────────────────────────


class MadeItemAllocationRules(DemandAllocationRules):
    """The shared allocation guards in made item demand terms. Made items are
    not substituted, so there is no item match to add."""

    terms = MADE_DEMAND_TERMS
