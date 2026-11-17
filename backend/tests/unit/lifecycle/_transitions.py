"""
Records the status transitions the lifecycle model's requests make, keyed by
the state machine catalogue's machine keys, for the generated transition
table (src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py).
"""

from src.modules.fulfillment.domain.services.lifecycle.transitions import ObservedTransition

# The model's status table kinds and the catalogue machines they feed; a
# position's entry is "status/kind" and feeds two machines.
_MACHINES = {
    "lot": ("lot_status",),
    "position": ("lot_position_status", "lot_position_kind"),
    "production_order": ("production_order_status",),
    "order": ("order_status",),
    "line": ("order_item_status",),
    "bought_demand": ("bought_item_demand_status",),
    "made_demand": ("made_item_demand_status",),
    "source_demand": ("source_item_demand_status",),
    "quote_request": ("quote_request_status",),
}

RECORDED: set[ObservedTransition] = set()


def _parts(kind: str, value: str | None) -> tuple[str | None, ...]:
    machines = _MACHINES[kind]
    if value is None:
        return (None,) * len(machines)
    return tuple(value.split("/")) if len(machines) > 1 else (value,)


def record(before: dict[str, str], after: dict[str, str], subject: str, trigger: str) -> None:
    """Adds every status change between the two status tables, made by
    `trigger` acting on `subject` (a status table key)."""
    subject_machine = _MACHINES[subject.split("#", 1)[0]][0]
    for key, value in after.items():
        kind = key.split("#", 1)[0]
        old_parts = _parts(kind, before.get(key))
        new_parts = _parts(kind, value)
        for machine, old, new in zip(_MACHINES[kind], old_parts, new_parts, strict=True):
            if old != new and new is not None:
                RECORDED.add(
                    ObservedTransition(
                        machine=machine,
                        from_state=old,
                        to_state=new,
                        trigger=trigger,
                        subject=subject_machine,
                    )
                )
