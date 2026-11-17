"""
Every lifecycle writer route of the web API, as the matrix calls it: a name,
the rows of the World it needs, and the request, sent with the edit versions
the client reads right before it, as a user acts on the rows they see. A
writer whose rows a shape lacks is skipped with that reason.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration import _lifecycle_seed as seed
from tests.integration._edit_versions import line_version
from tests.integration._edit_versions import lot_version
from tests.integration._edit_versions import order_version
from tests.integration._edit_versions import production_order_version
from tests.integration._tenant_day import tenant_today
from tests.integration.lifecycle_matrix._shapes import WEB
from tests.integration.lifecycle_matrix._shapes import World

# The permissions of the user every writer acts as.
EVERY_WRITE_PERMISSION = [
    Permission.WRITE_ORDERS,
    Permission.MANAGE_ORDERS,
    Permission.RECEIVE_DELIVERIES,
    Permission.WRITE_ALLOCATIONS,
    Permission.WRITE_DEMAND_ITEMS,
    Permission.MANAGE_DEMAND_ITEMS,
    Permission.WRITE_LOTS,
    Permission.MANAGE_LOTS,
    Permission.WRITE_PRODUCTION_ORDERS,
    Permission.MANAGE_PRODUCTION_ORDERS,
    Permission.WRITE_INSPECTIONS,
]

ORDERS = f"{WEB}/orders"
LOTS = f"{WEB}/production-lots"
PRODUCTION_ORDERS = f"{WEB}/production-orders"
_ALLOCATIONS = {
    "bought": f"{WEB}/bought-items-allocations",
    "source": f"{WEB}/source-item-allocations",
    "made": f"{WEB}/made-items-allocations",
}
_DEMANDS = {
    "bought": f"{WEB}/bought-items-demands",
    "source": f"{WEB}/source-item-demands",
    "made": f"{WEB}/made-items-demands",
}


@dataclass(frozen=True)
class Writer:
    name: str
    needs: tuple[str, ...]
    call: Callable[[World], Awaitable[httpx.Response]]
    # Families of `World.demand` the writer applies to, empty for any.
    families: tuple[str, ...] = ()


def _quantity(world: World, pieces: float) -> float:
    return float(world.notes.get("quantity", pieces))


async def _line_path(world: World) -> str:
    return f"{ORDERS}/{world.order}/items/{world.line}"


async def _line_version(world: World) -> int:
    """The line's version as the client shows it, read under the order the
    line is on now, so a moved line still sends one."""
    order = world.notes.get("line_order", world.order)
    return await line_version(world.client, order, world.line)  # type: ignore[arg-type]


async def deliver(world: World) -> httpx.Response:
    return await world.client.put(
        f"{_ALLOCATIONS['bought']}/order-item/{world.line}/deliver",
        params={"quantity": _quantity(world, 3)},
    )


async def deliver_rest(world: World) -> httpx.Response:
    return await world.client.put(f"{_ALLOCATIONS['bought']}/order-item/{world.line}/deliver")


async def deliver_lost(world: World) -> httpx.Response:
    return await world.client.put(
        f"{_ALLOCATIONS['bought']}/order-item/{world.line}/deliver",
        params={"quantity": 1},
        json={
            "quantity_rejected": 2,
            "rejection_reason": "transport_damage",
            "rejection_outcome": "lost",
        },
    )


async def deliver_redeliver(world: World) -> httpx.Response:
    return await world.client.put(
        f"{_ALLOCATIONS['bought']}/order-item/{world.line}/deliver",
        params={"quantity": 1},
        json={
            "quantity_rejected": 1,
            "rejection_reason": "supplier_damage",
            "rejection_outcome": "redeliver",
        },
    )


async def deliver_at_over_limit(world: World) -> httpx.Response:
    """11 of 10: within a 10 % over-delivery tolerance, beyond the line
    without one."""
    return await world.client.put(
        f"{_ALLOCATIONS['bought']}/order-item/{world.line}/deliver", params={"quantity": 11}
    )


async def deliver_beyond_over_limit(world: World) -> httpx.Response:
    return await world.client.put(
        f"{_ALLOCATIONS['bought']}/order-item/{world.line}/deliver", params={"quantity": 12}
    )


async def deliver_at_under_limit(world: World) -> httpx.Response:
    """9 of 10, which a 10 % under-delivery tolerance settles."""
    return await world.client.put(
        f"{_ALLOCATIONS['bought']}/order-item/{world.line}/deliver", params={"quantity": 9}
    )


async def deliver_all(world: World) -> httpx.Response:
    return await world.client.put(f"{ORDERS}/{world.order}/deliver-all-items")


async def deliver_all_lost(world: World) -> httpx.Response:
    """Deliver-all with one piece of the world's line lost at receipt."""
    return await world.client.put(
        f"{ORDERS}/{world.order}/deliver-all-items",
        json={
            "rejections": [
                {
                    "order_item_id": world.line,
                    "quantity_rejected": _quantity(world, 1),
                    "rejection_reason": "wrong_spec",
                    "rejection_outcome": "lost",
                    "create_replacement": False,
                }
            ]
        },
    )


async def correct(world: World) -> httpx.Response:
    order = world.notes.get("line_order", world.order)
    body = (await world.client.get(f"{ORDERS}/{order}")).json()
    line = next(i for i in body["items"] if i["id"] == world.line)
    return await world.client.post(
        f"{await _line_path(world)}/deliveries/{world.delivery}/correct",
        json={
            "quantity": _quantity(world, 1),
            "reason": "counted twice",
            "expected_edit_version": line["edit_version"],
        },
    )


async def close_short(world: World) -> httpx.Response:
    return await world.client.post(
        f"{await _line_path(world)}/close-short",
        params={"expected_edit_version": await _line_version(world)},
    )


async def reopen(world: World) -> httpx.Response:
    return await world.client.post(
        f"{await _line_path(world)}/reopen",
        params={"expected_edit_version": await _line_version(world)},
    )


async def cancel_line(world: World) -> httpx.Response:
    return await world.client.post(
        f"{await _line_path(world)}/cancel",
        params={"expected_edit_version": await _line_version(world)},
    )


async def remove_line(world: World) -> httpx.Response:
    return await world.client.delete(await _line_path(world))


async def move_line(world: World) -> httpx.Response:
    return await world.client.put(
        f"{await _line_path(world)}/move", json={"target_order_id": world.other_order}
    )


async def mark_ordered(world: World) -> httpx.Response:
    return await world.client.put(f"{await _line_path(world)}/mark-ordered")


async def mark_requested(world: World) -> httpx.Response:
    return await world.client.put(f"{await _line_path(world)}/mark-requested")


async def edit_line_quantity(world: World) -> httpx.Response:
    return await world.client.put(
        await _line_path(world),
        json={
            "quantity": _quantity(world, 6),
            "unit": world.notes.get("unit", "pcs"),
            "expected_edit_version": await _line_version(world),
        },
    )


async def cancel_order(world: World) -> httpx.Response:
    return await world.client.put(
        f"{ORDERS}/{world.order}/cancel",
        params={"expected_edit_version": await order_version(world.client, world.order)},  # type: ignore[arg-type]
    )


async def request_order(world: World) -> httpx.Response:
    return await world.client.put(f"{ORDERS}/{world.order}/request")


async def submit_order(world: World) -> httpx.Response:
    return await world.client.put(f"{ORDERS}/{world.order}/submit")


async def add_line_with_share(world: World) -> httpx.Response:
    assert world.demand is not None
    family, demand_id = world.demand
    item = {"bought": "bought_item_id", "source": "source_item_id"}[family]
    order = world.other_order
    return await world.client.post(
        f"{ORDERS}/{order}/items",
        json={
            "order_id": order,
            "supplier_id": 1,
            "project_id": 1,
            item: 1,
            "quantity": _quantity(world, 2),
            "unit": world.notes.get("unit", "pcs"),
            f"{family}_demand_allocations": [
                {"demand_item_id": demand_id, "quantity": _quantity(world, 2)}
            ],
        },
    )


async def allocate(world: World) -> httpx.Response:
    assert world.demand is not None
    family, demand_id = world.demand
    return await world.client.post(
        f"{_ALLOCATIONS[family]}/",
        json={"demand_item_id": demand_id, "order_item_id": world.line, "quantity": 1},
    )


async def update_allocation(world: World) -> httpx.Response:
    assert world.demand is not None
    family, demand_id = world.demand
    return await world.client.put(
        f"{_ALLOCATIONS[family]}/demand/{demand_id}/order-item/{world.line}",
        json={"quantity": _quantity(world, 4)},
    )


async def release_allocation(world: World) -> httpx.Response:
    assert world.demand is not None
    family, demand_id = world.demand
    return await world.client.delete(
        f"{_ALLOCATIONS[family]}/demand/{demand_id}/order-item/{world.line}"
    )


async def take_from_stock(world: World) -> httpx.Response:
    assert world.demand is not None
    family, demand_id = world.demand
    return await world.client.put(
        f"{_ALLOCATIONS[family]}/demand/{demand_id}/stock", json={"quantity": _quantity(world, 1)}
    )


async def fulfil_from_stock(world: World) -> httpx.Response:
    assert world.demand is not None
    family, demand_id = world.demand
    return await world.client.post(
        f"{_ALLOCATIONS[family]}/demand/{demand_id}/fulfill-from-stock",
        json={"quantity": _quantity(world, 1)},
    )


async def auto_allocate(world: World) -> httpx.Response:
    assert world.demand is not None
    family, demand_id = world.demand
    return await world.client.post(f"{_ALLOCATIONS[family]}/demand/{demand_id}/auto-allocate")


async def cancel_demand(world: World) -> httpx.Response:
    assert world.demand is not None
    family, demand_id = world.demand
    return await world.client.post(f"{_DEMANDS[family]}/{demand_id}/cancel")


async def fulfil_demand(world: World) -> httpx.Response:
    assert world.demand is not None
    family, demand_id = world.demand
    return await world.client.put(
        f"{_DEMANDS[family]}/{demand_id}/status", params={"new_status": "fulfilled"}
    )


async def cancel_neighbour(world: World) -> httpx.Response:
    assert world.neighbour is not None
    family, demand_id = world.neighbour
    return await world.client.post(f"{_DEMANDS[family]}/{demand_id}/cancel")


async def hold_lot(world: World) -> httpx.Response:
    return await world.client.post(f"{LOTS}/{world.lot}/hold", json={"reason": "check"})


async def resume_lot(world: World) -> httpx.Response:
    return await world.client.post(f"{LOTS}/{world.lot}/resume")


async def cancel_lot(world: World) -> httpx.Response:
    return await world.client.post(
        f"{LOTS}/{world.lot}/cancel",
        json={"expected_edit_version": await lot_version(world.client, world.lot), "reason": "x"},  # type: ignore[arg-type]
    )


async def force_complete_lot(world: World) -> httpx.Response:
    return await world.client.post(
        f"{LOTS}/{world.lot}/complete",
        json={"expected_edit_version": await lot_version(world.client, world.lot)},  # type: ignore[arg-type]
    )


async def edit_lot_quantity(world: World) -> httpx.Response:
    return await world.client.patch(
        f"{LOTS}/{world.lot}",
        json={"quantity": 6, "expected_edit_version": await lot_version(world.client, world.lot)},  # type: ignore[arg-type]
    )


async def assign_external(world: World) -> httpx.Response:
    return await world.client.post(
        f"{LOTS}/{world.lot}/positions/{world.free_position}/assign",
        json={"order_id": world.other_order, "unit": "pcs"},
    )


async def unassign_external(world: World) -> httpx.Response:
    return await world.client.delete(
        f"{LOTS}/{world.lot}/positions/{world.external_position}/assign"
    )


async def record_provision(world: World) -> httpx.Response:
    return await world.client.post(
        f"{LOTS}/{world.lot}/positions/{world.external_position}/provisions",
        json={"quantity": 1.0, "provision_date": seed.NOW.date().isoformat()},
    )


async def assign_internal(world: World) -> httpx.Response:
    return await world.client.post(
        f"{LOTS}/{world.lot}/positions/{world.free_position}/assign-internal",
        json={"orders": [{"quantity": 2}]},
    )


async def switch_source(world: World) -> httpx.Response:
    lot = (await world.client.get(f"{LOTS}/{world.lot}")).json()
    return await world.client.put(
        f"{LOTS}/{world.lot}/material-source",
        json={
            "bought_item_id": 1,
            "confirm_replace_demand": True,
            "expected_edit_version": lot.get("edit_version", 0),
        },
    )


async def approve_source(world: World) -> httpx.Response:
    lot = (await world.client.get(f"{LOTS}/{world.lot}")).json()
    return await world.client.post(
        f"{LOTS}/{world.lot}/source/approve",
        json={"expected_edit_version": lot.get("edit_version", 0)},
    )


async def scrap_lot(world: World) -> httpx.Response:
    lot = (await world.client.get(f"{LOTS}/{world.lot}")).json()
    position = min(lot["positions"], key=lambda p: p["sequence"])["id"] if lot["positions"] else 1
    return await world.client.post(
        f"{LOTS}/{world.lot}/scrap",
        json={
            "position_id": position,
            "quantity": 1,
            "reason": "tool_breakage",
            "create_replacement": True,
            "expected_edit_version": lot["edit_version"],
        },
    )


async def start(world: World) -> httpx.Response:
    return await world.client.post(f"{PRODUCTION_ORDERS}/{world.production_order}/start", json={})


async def pause(world: World) -> httpx.Response:
    return await world.client.post(f"{PRODUCTION_ORDERS}/{world.production_order}/pause", json={})


async def complete(world: World) -> httpx.Response:
    return await world.client.post(
        f"{PRODUCTION_ORDERS}/{world.production_order}/completions",
        json={"quantity": 1, "completion_date": tenant_today().isoformat()},
    )


async def reverse_completion(world: World) -> httpx.Response:
    return await world.client.post(
        f"{PRODUCTION_ORDERS}/{world.production_order}/completions/{world.completion}/reverse",
        json={"reason": "miscounted"},
    )


async def scrap_order(world: World) -> httpx.Response:
    order = world.production_order
    return await world.client.post(
        f"{PRODUCTION_ORDERS}/{order}/scrap",
        json={
            "quantity": 1,
            "reason": "tool_breakage",
            "create_replacement": False,
            "expected_edit_version": await production_order_version(world.client, order),  # type: ignore[arg-type]
            "expected_lot_edit_version": await lot_version(world.client, world.lot),  # type: ignore[arg-type]
        },
    )


async def cancel_production_order(world: World) -> httpx.Response:
    order = world.production_order
    return await world.client.post(
        f"{PRODUCTION_ORDERS}/{order}/cancel",
        json={"expected_edit_version": await production_order_version(world.client, order)},  # type: ignore[arg-type]
    )


async def split(world: World) -> httpx.Response:
    return await world.client.post(
        f"{PRODUCTION_ORDERS}/{world.production_order}/split", json={"quantities": [2, 3]}
    )


_LINE = ("order", "line")
_DEMAND_LINE = ("demand", "line")

WRITERS: list[Writer] = [
    Writer("deliver", ("line",), deliver),
    Writer("deliver_rest", ("line",), deliver_rest),
    Writer("deliver_lost", ("line",), deliver_lost),
    Writer("deliver_redeliver", ("line",), deliver_redeliver),
    Writer("deliver_at_over_limit", ("line",), deliver_at_over_limit),
    Writer("deliver_beyond_over_limit", ("line",), deliver_beyond_over_limit),
    Writer("deliver_at_under_limit", ("line",), deliver_at_under_limit),
    Writer("deliver_all", ("order",), deliver_all),
    Writer("deliver_all_lost", ("order", "line"), deliver_all_lost),
    Writer("correct", (*_LINE, "delivery"), correct),
    Writer("close_short", _LINE, close_short),
    Writer("reopen", _LINE, reopen),
    Writer("cancel_line", _LINE, cancel_line),
    Writer("remove_line", _LINE, remove_line),
    Writer("move_line", (*_LINE, "other_order"), move_line),
    Writer("mark_ordered", _LINE, mark_ordered),
    Writer("mark_requested", _LINE, mark_requested),
    Writer("edit_line_quantity", _LINE, edit_line_quantity),
    Writer("cancel_order", ("order",), cancel_order),
    Writer("request_order", ("order",), request_order),
    Writer("submit_order", ("order",), submit_order),
    Writer(
        "add_line_with_share",
        ("demand", "other_order"),
        add_line_with_share,
        families=("bought", "source"),
    ),
    Writer("allocate", _DEMAND_LINE, allocate, families=("bought", "source")),
    Writer("update_allocation", _DEMAND_LINE, update_allocation, families=("bought", "source")),
    Writer("release_allocation", _DEMAND_LINE, release_allocation, families=("bought", "source")),
    Writer("take_from_stock", ("demand",), take_from_stock),
    Writer("fulfil_from_stock", ("demand",), fulfil_from_stock),
    Writer("auto_allocate", ("demand",), auto_allocate, families=("bought", "source")),
    Writer("cancel_demand", ("demand",), cancel_demand),
    Writer("fulfil_demand", ("demand",), fulfil_demand),
    Writer("cancel_neighbour", ("neighbour",), cancel_neighbour),
    Writer("hold_lot", ("lot",), hold_lot),
    Writer("resume_lot", ("lot",), resume_lot),
    Writer("cancel_lot", ("lot",), cancel_lot),
    Writer("force_complete_lot", ("lot",), force_complete_lot),
    Writer("edit_lot_quantity", ("lot",), edit_lot_quantity),
    Writer("assign_external", ("lot", "free_position", "other_order"), assign_external),
    Writer("unassign_external", ("lot", "external_position"), unassign_external),
    Writer("record_provision", ("lot", "external_position"), record_provision),
    Writer("assign_internal", ("lot", "free_position"), assign_internal),
    Writer("switch_source", ("lot",), switch_source),
    Writer("approve_source", ("lot",), approve_source),
    # A lot scrap targets a position with open internal work.
    Writer("scrap_lot", ("lot", "production_order"), scrap_lot),
    Writer("start", ("production_order",), start),
    Writer("pause", ("production_order",), pause),
    Writer("complete", ("production_order",), complete),
    Writer("reverse_completion", ("production_order", "completion"), reverse_completion),
    Writer("scrap_order", ("production_order", "lot"), scrap_order),
    Writer("cancel_production_order", ("production_order",), cancel_production_order),
    Writer("split", ("production_order",), split),
]


def skip_reason(writer: Writer, world: World) -> str | None:
    """Why `writer` cannot act on `world`, or None when it can."""
    missing = [need for need in writer.needs if getattr(world, need) is None]
    if missing:
        return f"the shape has no {', '.join(missing)} for {writer.name}"
    if writer.families and world.demand is not None and world.demand[0] not in writer.families:
        return f"{writer.name} takes {' or '.join(writer.families)} demands, not {world.demand[0]}"
    return None
