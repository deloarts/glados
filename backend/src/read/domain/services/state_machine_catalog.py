"""
Lists every lifecycle in the system as the code runs it, for the handbook.

A machine is derived when an ordered decision table computes its status from
recorded facts and intents (src/modules/fulfillment/domain/services/lifecycle/rules.py), and an
intent machine when the status is set by user actions alone. A derived
machine lists the rows of its table in evaluation order, and any machine lists
the user actions its intent table accepts, with the statuses each starts from.
Rows and actions are read from the DerivationTable and IntentTable objects
that the reconciler and the use cases execute, so the catalogue shows exactly
what the code does. The catalogue item lists the status moves of
catalogue_item_status.py as edges, and the project the status moves of
lifecycle/project.py as edges beside their intents. A lifecycle also lists the
status changes the code makes, generated from the lifecycle model
(lifecycle/observed_transitions.py), with the rows and permissions behind
them and what else each request changed.

Each row carries a `text_key`, `<table>.r<number>` for a derivation row and
`<table>.<action>` for an action, under which the frontend keeps its
translated text (catalogue_text_keys lists every key it needs). The English
condition and effect texts stay with the row.

Nothing is cached: every call builds the catalogue from the live tables.
"""

from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Any
from typing import cast

from src.modules.catalogue.domain.policies.catalogue_item_status import STATUS_MOVES
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.policies.lifecycle import BOUGHT_DEMAND_STATUS
from src.modules.fulfillment.domain.policies.lifecycle import DEMAND_INTENTS
from src.modules.fulfillment.domain.policies.lifecycle import LOT_INTENTS
from src.modules.fulfillment.domain.policies.lifecycle import LOT_POSITION_INTENTS
from src.modules.fulfillment.domain.policies.lifecycle import LOT_STATUS
from src.modules.fulfillment.domain.policies.lifecycle import MADE_DEMAND_STATUS
from src.modules.fulfillment.domain.policies.lifecycle import ORDER_INTENTS
from src.modules.fulfillment.domain.policies.lifecycle import ORDER_ITEM_INTENTS
from src.modules.fulfillment.domain.policies.lifecycle import ORDER_ITEM_STATUS
from src.modules.fulfillment.domain.policies.lifecycle import ORDER_STATUS
from src.modules.fulfillment.domain.policies.lifecycle import POSITION_KIND
from src.modules.fulfillment.domain.policies.lifecycle import POSITION_STATUS
from src.modules.fulfillment.domain.policies.lifecycle import PRODUCTION_ORDER_INTENTS
from src.modules.fulfillment.domain.policies.lifecycle import PRODUCTION_ORDER_STATUS
from src.modules.fulfillment.domain.policies.lifecycle import QUOTE_REQUEST_INTENTS
from src.modules.fulfillment.domain.policies.lifecycle import QUOTE_REQUEST_STATUS
from src.modules.fulfillment.domain.policies.lifecycle import SOURCE_DEMAND_STATUS
from src.modules.fulfillment.domain.policies.lifecycle import TRANSITIONS
from src.modules.fulfillment.domain.policies.lifecycle import DerivationTable
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.services.intent_table import IntentTable
from src.modules.workspace.domain.policies.project_lifecycle import PROJECT_INTENTS
from src.modules.workspace.domain.policies.project_lifecycle import PROJECT_STATUS_MOVES
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

# The action of a status move that is no lifecycle intent: a catalogue item's
# move between its statuses.
SET_STATUS = "set_status"


class MachineKind(Enum):
    """DERIVED: a decision table computes the status from facts and intents.
    INTENT: user actions set the status."""

    DERIVED = "derived"
    INTENT = "intent"


@dataclass(frozen=True)
class MachineState:
    value: str
    initial: bool
    terminal: bool


@dataclass(frozen=True)
class MachineEdge:
    from_state: str
    to_state: str


@dataclass(frozen=True)
class RuleRow:
    """One row of a derivation table. `results` lists the statuses the row
    can give, one for most rows; a row with several names them in its own
    `result` text, which `result_text_key` translates."""

    number: int
    text_key: str
    condition: str
    result: str
    results: tuple[str, ...]
    result_text_key: str | None = None


@dataclass(frozen=True)
class IntentRow:
    """One user action. `allowed_from` lists the statuses it starts from,
    None for any status; `target` is the status a status move sets, None for
    a lifecycle action. `condition` and `permission` are empty when the
    action needs nothing beyond its statuses and its base permission."""

    action: str
    text_key: str
    allowed_from: tuple[str, ...] | None
    condition: str
    permission: str
    effect: str
    target: str | None = None


@dataclass(frozen=True)
class Implication:
    """A status change on another machine that the same request made."""

    machine: str
    from_state: str | None
    to_state: str


@dataclass(frozen=True)
class TransitionRow:
    """One status change the code makes (lifecycle/transitions.py), its
    trigger translated under `triggers.<trigger>`. A `cascade` row is one a
    request on another aggregate made, `subject` naming that aggregate's
    machine. `rule_text_keys` are the derivation rows that give
    `to_state`, `intent_text_keys` the actions of this machine the trigger
    performs (their condition and permission apply), and `implications`
    what the same trigger changes on other aggregates."""

    from_state: str | None
    to_state: str
    trigger: str
    subject: str
    cascade: bool
    rule_text_keys: tuple[str, ...]
    intent_text_keys: tuple[str, ...]
    implications: tuple[Implication, ...]


@dataclass(frozen=True)
class StateMachineEntry:
    """One registry entry. `rules_key` names the derivation rows' texts; it
    defaults to the table's key and lets the three demand tables, which one
    function builds with the same rows, share their texts."""

    key: str
    entity: str
    enum_cls: type[Enum]
    derivation: DerivationTable[Any, Any] | None = None
    intents: IntentTable[Any, Any] | None = None
    rules_key: str | None = None
    extra_intents: tuple[IntentRow, ...] = ()
    edges: tuple[MachineEdge, ...] = ()


@dataclass(frozen=True)
class MachineGraph:
    key: str
    entity: str
    kind: MachineKind
    description: str | None
    states: list[MachineState] = field(default_factory=list)
    edges: list[MachineEdge] = field(default_factory=list)
    rules: list[RuleRow] = field(default_factory=list)
    intents: list[IntentRow] = field(default_factory=list)
    transitions: list[TransitionRow] = field(default_factory=list)


def _catalogue_item_moves() -> tuple[tuple[IntentRow, ...], tuple[MachineEdge, ...]]:
    """The status moves of an existing catalogue item, one row per target
    status, and their edges. Creating an item is not a move."""
    moves = [m for m in STATUS_MOVES if m.from_status is not None]
    edges = tuple(MachineEdge(cast(str, m.from_status), m.to_status) for m in moves)
    rows = []
    for target in dict.fromkeys(m.to_status for m in moves):
        into = [m for m in moves if m.to_status == target]
        rows.append(
            IntentRow(
                action=SET_STATUS,
                text_key=f"catalogue_item.to_{target}",
                allowed_from=tuple(cast(str, m.from_status) for m in into),
                condition="",
                permission="",
                effect=into[0].effect,
                target=target,
            )
        )
    return tuple(rows), edges


_CATALOGUE_MOVE_ROWS, _CATALOGUE_MOVE_EDGES = _catalogue_item_moves()


def _project_move_edges() -> tuple[MachineEdge, ...]:
    """One edge per start status of each status move of the project."""
    edges: list[MachineEdge] = []
    for action, target in PROJECT_STATUS_MOVES.items():
        rule = PROJECT_INTENTS.rule_for(action)
        starts = (rule.allowed_from or ()) if rule is not None else ()
        edges.extend(MachineEdge(start, target) for start in starts)
    return tuple(edges)


# Registry order is the order machines appear in the catalogue.
STATE_MACHINE_REGISTRY: list[StateMachineEntry] = [
    StateMachineEntry(
        key="order_status",
        entity="Order",
        enum_cls=OrderStatus,
        derivation=ORDER_STATUS,
        intents=ORDER_INTENTS,
    ),
    StateMachineEntry(
        key="order_item_status",
        entity="Order item",
        enum_cls=OrderItemStatus,
        derivation=ORDER_ITEM_STATUS,
        intents=ORDER_ITEM_INTENTS,
    ),
    StateMachineEntry(
        key="production_order_status",
        entity="Production order",
        enum_cls=ProductionOrderStatus,
        derivation=PRODUCTION_ORDER_STATUS,
        intents=PRODUCTION_ORDER_INTENTS,
    ),
    StateMachineEntry(
        key="lot_position_kind",
        entity="Lot position kind",
        enum_cls=LotPositionKind,
        derivation=POSITION_KIND,
        intents=LOT_POSITION_INTENTS,
    ),
    StateMachineEntry(
        key="lot_position_status",
        entity="Lot position",
        enum_cls=LotPositionStatus,
        derivation=POSITION_STATUS,
    ),
    StateMachineEntry(
        key="lot_status",
        entity="Lot",
        enum_cls=LotStatus,
        derivation=LOT_STATUS,
        intents=LOT_INTENTS,
    ),
    StateMachineEntry(
        key="bought_item_demand_status",
        entity="Bought item demand",
        enum_cls=BoughtItemDemandStatus,
        derivation=BOUGHT_DEMAND_STATUS,
        intents=DEMAND_INTENTS,
        rules_key="demand_status",
    ),
    StateMachineEntry(
        key="made_item_demand_status",
        entity="Made item demand",
        enum_cls=MadeItemDemandStatus,
        derivation=MADE_DEMAND_STATUS,
        intents=DEMAND_INTENTS,
        rules_key="demand_status",
    ),
    StateMachineEntry(
        key="source_item_demand_status",
        entity="Source item demand",
        enum_cls=SourceItemDemandStatus,
        derivation=SOURCE_DEMAND_STATUS,
        intents=DEMAND_INTENTS,
        rules_key="demand_status",
    ),
    StateMachineEntry(
        key="catalogue_item_status",
        entity="Catalogue item",
        enum_cls=BoughtItemCatalogueStatus,
        extra_intents=_CATALOGUE_MOVE_ROWS,
        edges=_CATALOGUE_MOVE_EDGES,
    ),
    StateMachineEntry(
        key="project_status",
        entity="Project",
        enum_cls=ProjectStatus,
        intents=PROJECT_INTENTS,
        edges=_project_move_edges(),
    ),
    StateMachineEntry(
        key="quote_request_status",
        entity="Quote request",
        enum_cls=QuoteRequestStatus,
        derivation=QUOTE_REQUEST_STATUS,
        intents=QUOTE_REQUEST_INTENTS,
    ),
]


def rule_rows(entry: StateMachineEntry) -> list[RuleRow]:
    """The derivation rows of the entry in evaluation order, the fallback
    last; empty for an intent machine."""
    table = entry.derivation
    if table is None:
        return []
    namespace = entry.rules_key or table.key
    return [
        RuleRow(
            number=row.number,
            text_key=f"{namespace}.r{row.number}",
            condition=row.condition,
            result=row.result,
            results=tuple(str(result.value) for result in row.results),
            result_text_key=(f"{namespace}.r{row.number}Result" if len(row.results) > 1 else None),
        )
        for row in table.rows
    ]


def intent_rows(entry: StateMachineEntry) -> list[IntentRow]:
    """The entry's extra rows, then its intent table's rules in table order."""
    rows = list(entry.extra_intents)
    table = entry.intents
    if table is not None:
        rows.extend(
            IntentRow(
                action=rule.action.value,
                text_key=f"{table.key}.{rule.action.value}",
                allowed_from=rule.allowed_from,
                condition=rule.condition,
                permission=rule.permission,
                effect=rule.effect,
            )
            for rule in table.rules
        )
    return rows


# The lifecycle action each request of the lifecycle model performs; a
# request that only records work on the floor names none. Every trigger of
# the transition table is listed, so a new one has to be classified here
# (test_state_machine_catalog.py).
_A = LifecycleAction
TRIGGER_ACTIONS: dict[str, tuple[LifecycleAction, ...]] = {
    "allocate": (_A.ALLOCATE,),
    "allocate_source": (_A.ALLOCATE,),
    "assign_external": (_A.ASSIGN_EXTERNAL,),
    "assign_internal": (_A.ASSIGN_INTERNAL,),
    "award": (_A.AWARD,),
    "cancel_bought_demand_request": (_A.CANCEL,),
    "cancel_line": (_A.CANCEL,),
    "cancel_lot_request": (_A.CANCEL,),
    "cancel_made_demand_request": (_A.CANCEL,),
    "cancel_order": (_A.CANCEL,),
    "cancel_production_order": (_A.CANCEL,),
    "cancel_source_demand_request": (_A.CANCEL,),
    "close_short": (_A.CLOSE_SHORT,),
    "complete": (_A.RECORD_COMPLETION,),
    "correct": (_A.CORRECT_DELIVERY,),
    "create_lot_for_demand": (),
    "deliver": (_A.DELIVER,),
    "deliver_all": (_A.DELIVER,),
    "force_complete": (_A.FORCE_COMPLETE,),
    "fulfil_bought_demand": (_A.FULFIL,),
    "fulfil_made_demand": (_A.FULFIL,),
    "fulfil_source_demand": (_A.FULFIL,),
    "hold": (_A.HOLD,),
    "mark_ordered": (_A.MARK_ORDERED,),
    "mark_requested": (_A.MARK_REQUESTED,),
    "merge": (_A.MERGE,),
    "move": (_A.MOVE,),
    "pause": (_A.PAUSE,),
    "release": (_A.ALLOCATE,),
    "reopen": (_A.REOPEN,),
    "request_order": (_A.MARK_REQUESTED,),
    "resume_lot": (_A.RESUME,),
    "reverse_completion": (_A.REVERSE_COMPLETION,),
    "scrap": (_A.SCRAP,),
    "source_from_stock": (_A.ALLOCATE,),
    "split": (_A.SPLIT,),
    "start": (_A.START, _A.RESUME),
    "submit_order": (_A.MARK_ORDERED,),
    "take_from_stock": (_A.ALLOCATE,),
    "unassign_external": (_A.UNASSIGN_EXTERNAL,),
    "update_allocation": (_A.ALLOCATE,),
}

# The position's kind and status are two machines of one aggregate.
_AGGREGATE_OF = {"lot_position_kind": "lot_position_status"}


def _aggregate(machine: str) -> str:
    return _AGGREGATE_OF.get(machine, machine)


def transition_rows(
    entry: StateMachineEntry, rules: list[RuleRow], intents: list[IntentRow]
) -> list[TransitionRow]:
    """The entry's observed transitions, each with the derivation rows that
    give its target, the actions its trigger performs on this machine and
    what the same trigger changes on other aggregates."""
    rows = []
    for t in TRANSITIONS:
        if t.machine != entry.key:
            continue
        own = _aggregate(t.machine) == _aggregate(t.subject)
        actions = {a.value for a in TRIGGER_ACTIONS.get(t.trigger, ())} if own else set()
        implications = sorted(
            {
                Implication(o.machine, o.from_state, o.to_state)
                for o in TRANSITIONS
                if own
                and o.trigger == t.trigger
                and o.subject == t.subject
                and _aggregate(o.machine) != _aggregate(t.machine)
            },
            key=lambda i: (i.machine, i.from_state or "", i.to_state),
        )
        rows.append(
            TransitionRow(
                from_state=t.from_state,
                to_state=t.to_state,
                trigger=t.trigger,
                subject=t.subject,
                cascade=not own,
                rule_text_keys=tuple(r.text_key for r in rules if t.to_state in r.results),
                intent_text_keys=tuple(i.text_key for i in intents if i.action in actions),
                implications=tuple(implications),
            )
        )
    return rows


def _initial_value(enum_cls: type[Enum]) -> str | None:
    """The value of the enum's `default()`, None when it defines none."""
    default_fn = getattr(enum_cls, "default", None)
    if not callable(default_fn):
        return None
    return str(cast(Enum, default_fn()).value)


def _terminal_values(
    values: list[str],
    intents: list[IntentRow],
    edges: list[MachineEdge],
    transitions: list[TransitionRow],
) -> set[str]:
    """The states no action, no edge and no observed transition leaves, so
    a state a cascade moves on from, such as a delivered order a correction
    reopens, is not drawn as final. A machine whose actions start from any
    status and that has no edges has no terminal state."""
    starts = {e.from_state for e in edges}
    for row in intents:
        if row.allowed_from is not None:
            starts.update(row.allowed_from)
    if not starts:
        return set()
    starts.update(t.from_state for t in transitions if t.from_state is not None)
    return {value for value in values if value not in starts}


def build_machine_graph(entry: StateMachineEntry) -> MachineGraph:
    """Pure: the full description of one machine. No I/O."""
    values = [str(member.value) for member in entry.enum_cls]
    edges = list(entry.edges)
    intents = intent_rows(entry)
    rules = rule_rows(entry)
    initial = _initial_value(entry.enum_cls)
    transitions = transition_rows(entry, rules, intents)
    terminal = _terminal_values(values, intents, edges, transitions)
    return MachineGraph(
        key=entry.key,
        entity=entry.entity,
        kind=MachineKind.DERIVED if entry.derivation is not None else MachineKind.INTENT,
        description=entry.enum_cls.__doc__,
        states=[MachineState(v, initial=v == initial, terminal=v in terminal) for v in values],
        edges=edges,
        rules=rules,
        intents=intents,
        transitions=transitions,
    )


def build_state_machine_catalog(
    registry: list[StateMachineEntry] | None = None,
) -> list[MachineGraph]:
    """Pure: one graph per registry entry, in registry order, built fresh on
    every call."""
    entries = STATE_MACHINE_REGISTRY if registry is None else registry
    return [build_machine_graph(entry) for entry in entries]


def catalogue_text_keys(registry: list[StateMachineEntry] | None = None) -> list[str]:
    """Every translation the frontend needs for the catalogue's rows, as
    paths below its `stateMachines` locale block, once each, in catalogue
    order: `rows.<text_key>` for a derivation row and for the result text of
    a row with several results, and `intentRows.<text_key>.effect` for an
    action, plus `.condition` and `.permission` where the action has them,
    and `machines.<key>` and `triggers.<trigger>` for the transition tables."""
    keys: dict[str, None] = {}
    for graph in build_state_machine_catalog(registry):
        for rule in graph.rules:
            keys[f"rows.{rule.text_key}"] = None
            if rule.result_text_key is not None:
                keys[f"rows.{rule.result_text_key}"] = None
        for intent in graph.intents:
            keys[f"intentRows.{intent.text_key}.effect"] = None
            if intent.condition:
                keys[f"intentRows.{intent.text_key}.condition"] = None
            if intent.permission:
                keys[f"intentRows.{intent.text_key}.permission"] = None
        for transition in graph.transitions:
            keys[f"machines.{graph.key}"] = None
            keys[f"machines.{transition.subject}"] = None
            keys[f"triggers.{transition.trigger}"] = None
    return list(keys)
