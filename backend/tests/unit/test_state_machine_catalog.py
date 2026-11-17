"""
The state machine catalogue (src/read/domain/services/state_machine_catalog.py):
its registry, each machine's kind, and that every rule row and action is
the row the code runs, read from the same DerivationTable and IntentTable
objects, so the catalogue cannot drift from the derivation or the guards.
"""

import importlib
import inspect

import pytest

from src.modules.catalogue.domain.policies.catalogue_item_status import STATUS_MOVES
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
from src.modules.platform.domain.services.intent_table import IntentTable
from src.modules.workspace.domain.services.lifecycle.project import PROJECT_INTENTS
from src.modules.workspace.domain.services.lifecycle.project import PROJECT_STATUS_MOVES
from src.read.domain.services.state_machine_catalog import SET_STATUS
from src.read.domain.services.state_machine_catalog import STATE_MACHINE_REGISTRY
from src.read.domain.services.state_machine_catalog import TRIGGER_ACTIONS
from src.read.domain.services.state_machine_catalog import MachineKind
from src.read.domain.services.state_machine_catalog import build_machine_graph
from src.read.domain.services.state_machine_catalog import build_state_machine_catalog
from src.read.domain.services.state_machine_catalog import catalogue_text_keys
from tests.layer_packages import layer_module_names

_EXPECTED_REGISTRY = [
    ("order_status", "Order", MachineKind.DERIVED),
    ("order_item_status", "Order item", MachineKind.DERIVED),
    ("production_order_status", "Production order", MachineKind.DERIVED),
    ("lot_position_kind", "Lot position kind", MachineKind.DERIVED),
    ("lot_position_status", "Lot position", MachineKind.DERIVED),
    ("lot_status", "Lot", MachineKind.DERIVED),
    ("bought_item_demand_status", "Bought item demand", MachineKind.DERIVED),
    ("made_item_demand_status", "Made item demand", MachineKind.DERIVED),
    ("source_item_demand_status", "Source item demand", MachineKind.DERIVED),
    ("catalogue_item_status", "Catalogue item", MachineKind.INTENT),
    ("project_status", "Project", MachineKind.INTENT),
    ("quote_request_status", "Quote request", MachineKind.DERIVED),
]


def _graph(key: str):
    return next(g for g in build_state_machine_catalog() if g.key == key)


def _lifecycle_tables() -> tuple[set[int], set[int]]:
    """Every DerivationTable and IntentTable defined in the lifecycle
    package, by identity, found independently of the registry."""
    derivations: set[int] = set()
    intents: set[int] = set()
    for module_name in layer_module_names("domain/services/lifecycle", recursive=False):
        module = importlib.import_module(module_name)
        for _, value in inspect.getmembers(module):
            if isinstance(value, DerivationTable):
                derivations.add(id(value))
            elif isinstance(value, IntentTable):
                intents.add(id(value))
    return derivations, intents


# ── Registry ────────────────────────────────────────────────────────────


def test_the_registry_lists_the_twelve_machines_with_their_kinds():
    graphs = build_state_machine_catalog()
    assert [(g.key, g.entity, g.kind) for g in graphs] == _EXPECTED_REGISTRY


def test_registry_keys_are_unique():
    keys = [entry.key for entry in STATE_MACHINE_REGISTRY]
    assert len(keys) == len(set(keys))


def test_every_derivation_and_intent_table_of_the_lifecycle_package_is_in_the_catalogue():
    """A new table cannot be left out: the package is scanned, not trusted."""
    derivations, intents = _lifecycle_tables()
    registered_derivations = {
        id(e.derivation) for e in STATE_MACHINE_REGISTRY if e.derivation is not None
    }
    registered_intents = {id(e.intents) for e in STATE_MACHINE_REGISTRY if e.intents is not None}
    assert derivations == registered_derivations
    assert intents == registered_intents


@pytest.mark.parametrize(
    ("key", "derivation", "intents"),
    [
        ("order_status", ORDER_STATUS, ORDER_INTENTS),
        ("order_item_status", ORDER_ITEM_STATUS, ORDER_ITEM_INTENTS),
        ("production_order_status", PRODUCTION_ORDER_STATUS, PRODUCTION_ORDER_INTENTS),
        ("lot_position_kind", POSITION_KIND, LOT_POSITION_INTENTS),
        ("lot_position_status", POSITION_STATUS, None),
        ("lot_status", LOT_STATUS, LOT_INTENTS),
        ("bought_item_demand_status", BOUGHT_DEMAND_STATUS, DEMAND_INTENTS),
        ("made_item_demand_status", MADE_DEMAND_STATUS, DEMAND_INTENTS),
        ("source_item_demand_status", SOURCE_DEMAND_STATUS, DEMAND_INTENTS),
        ("project_status", None, PROJECT_INTENTS),
        ("quote_request_status", QUOTE_REQUEST_STATUS, QUOTE_REQUEST_INTENTS),
    ],
)
def test_each_machine_reads_the_tables_the_code_runs(key, derivation, intents):
    entry = next(e for e in STATE_MACHINE_REGISTRY if e.key == key)
    assert entry.derivation is derivation
    assert entry.intents is intents


# ── Rule rows equal the executed rows ───────────────────────────────────


@pytest.mark.parametrize("entry", STATE_MACHINE_REGISTRY, ids=lambda e: e.key)
def test_rule_rows_are_the_derivation_rows_in_evaluation_order(entry):
    graph = build_machine_graph(entry)
    if entry.derivation is None:
        assert graph.rules == []
        return
    rows = entry.derivation.rows
    assert [r.number for r in graph.rules] == [row.number for row in rows]
    assert [r.condition for r in graph.rules] == [row.condition for row in rows]
    assert [r.result for r in graph.rules] == [row.result for row in rows]
    assert [r.results for r in graph.rules] == [
        tuple(str(v.value) for v in row.results) for row in rows
    ]
    assert graph.rules[-1].condition == "otherwise"


def test_a_row_with_several_results_names_its_result_text():
    rules = _graph("order_status").rules
    with_text = [r for r in rules if r.result_text_key is not None]
    assert [(r.number, r.result_text_key) for r in with_text] == [(2, "order_status.r2Result")]
    assert with_text[0].results == ("ordered", "requested", "draft")


def test_the_three_demand_machines_share_their_row_texts():
    keys = {
        key: [r.text_key for r in _graph(key).rules]
        for key in (
            "bought_item_demand_status",
            "made_item_demand_status",
            "source_item_demand_status",
        )
    }
    expected = [f"demand_status.r{n}" for n in range(1, 7)]
    assert all(value == expected for value in keys.values())


# ── Intent rows equal the executed rules ────────────────────────────────


@pytest.mark.parametrize(
    "entry", [e for e in STATE_MACHINE_REGISTRY if e.intents is not None], ids=lambda e: e.key
)
def test_intent_rows_are_the_intent_table_rules(entry):
    graph = build_machine_graph(entry)
    table_rows = graph.intents[len(entry.extra_intents) :]
    rules = entry.intents.rules
    assert [r.action for r in table_rows] == [rule.action.value for rule in rules]
    assert [r.allowed_from for r in table_rows] == [rule.allowed_from for rule in rules]
    assert [r.condition for r in table_rows] == [rule.condition for rule in rules]
    assert [r.permission for r in table_rows] == [rule.permission for rule in rules]
    assert [r.effect for r in table_rows] == [rule.effect for rule in rules]
    assert [r.text_key for r in table_rows] == [
        f"{entry.intents.key}.{rule.action.value}" for rule in rules
    ]


def test_the_catalogue_item_moves_are_the_status_moves_of_the_code():
    graph = _graph("catalogue_item_status")
    moves = [m for m in STATUS_MOVES if m.from_status is not None]
    assert {(e.from_state, e.to_state) for e in graph.edges} == {
        (m.from_status, m.to_status) for m in moves
    }
    for row in graph.intents:
        into = [m for m in moves if m.to_status == row.target]
        assert row.action == SET_STATUS
        assert set(row.allowed_from or ()) == {m.from_status for m in into}
        assert {row.effect} == {m.effect for m in into}
    assert {row.target for row in graph.intents} == {m.to_status for m in moves}


def test_the_project_lists_its_status_moves_and_their_edges():
    graph = _graph("project_status")
    assert [(r.action, r.allowed_from, r.effect) for r in graph.intents] == [
        (rule.action.value, rule.allowed_from, rule.effect) for rule in PROJECT_INTENTS.rules
    ]
    assert {(e.from_state, e.to_state) for e in graph.edges} == {
        (start, target)
        for action, target in PROJECT_STATUS_MOVES.items()
        for start in PROJECT_INTENTS.rule_for(action).allowed_from
    }


# ── States ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("entry", STATE_MACHINE_REGISTRY, ids=lambda e: e.key)
def test_states_are_the_enum_members_with_one_initial_state(entry):
    graph = build_machine_graph(entry)
    assert [s.value for s in graph.states] == [m.value for m in entry.enum_cls]
    assert [s.value for s in graph.states if s.initial] == [entry.enum_cls.default().value]


@pytest.mark.parametrize(
    ("key", "terminal"),
    [
        # A delivered order takes a new line, and one canceled only because
        # every line is canceled does too.
        ("order_status", set()),
        ("order_item_status", {"canceled"}),
        # A completed order leaves COMPLETED again when a completion is reversed.
        ("production_order_status", {"canceled"}),
        ("lot_position_kind", set()),
        ("lot_position_status", set()),
        ("lot_status", {"completed", "canceled", "scrapped"}),
        # A fulfilled demand opens again when a delivery is corrected.
        ("bought_item_demand_status", {"canceled"}),
        ("catalogue_item_status", set()),
        ("project_status", set()),
    ],
)
def test_a_state_is_terminal_when_no_action_and_no_edge_leaves_it(key, terminal):
    assert {s.value for s in _graph(key).states if s.terminal} == terminal


def test_a_terminal_state_is_no_starting_status_of_any_action():
    for graph in build_state_machine_catalog():
        starts = {v for row in graph.intents for v in (row.allowed_from or ())}
        terminal = {s.value for s in graph.states if s.terminal}
        assert not (terminal & starts), graph.key


def test_edges_only_reference_declared_states():
    for graph in build_state_machine_catalog():
        declared = {s.value for s in graph.states}
        for edge in graph.edges:
            assert {edge.from_state, edge.to_state} <= declared, graph.key


def test_allowed_from_only_names_declared_states():
    for graph in build_state_machine_catalog():
        declared = {s.value for s in graph.states}
        for row in graph.intents:
            assert set(row.allowed_from or ()) <= declared, (graph.key, row.action)


def test_rule_results_only_name_declared_states():
    for graph in build_state_machine_catalog():
        declared = {s.value for s in graph.states}
        for row in graph.rules:
            assert set(row.results) <= declared, (graph.key, row.number)


# ── Text keys ──────────────────────────────────────────────────────────


def test_text_keys_cover_every_row_and_every_text_field():
    keys = catalogue_text_keys()
    assert len(keys) == len(set(keys))
    for graph in build_state_machine_catalog():
        for rule in graph.rules:
            assert f"rows.{rule.text_key}" in keys
        for intent in graph.intents:
            assert f"intentRows.{intent.text_key}.effect" in keys
            assert (f"intentRows.{intent.text_key}.condition" in keys) is bool(intent.condition)
            assert (f"intentRows.{intent.text_key}.permission" in keys) is bool(intent.permission)
    assert "rows.order_status.r2Result" in keys


def test_description_is_the_enum_class_docstring():
    entry = next(e for e in STATE_MACHINE_REGISTRY if e.key == "lot_status")
    assert build_machine_graph(entry).description == entry.enum_cls.__doc__


def test_description_is_none_when_the_enum_has_no_docstring():
    """SourceItemDemandStatus has no class docstring (only a module
    docstring); the catalogue must not fabricate one."""
    entry = next(e for e in STATE_MACHINE_REGISTRY if e.key == "source_item_demand_status")
    assert entry.enum_cls.__doc__ is None
    assert build_machine_graph(entry).description is None


def test_every_trigger_of_the_transition_table_is_classified() -> None:
    """A new trigger of the lifecycle model names the actions it performs,
    or none, before the handbook can show its condition and permission."""
    triggers = {t.trigger for t in TRANSITIONS}

    assert sorted(triggers - TRIGGER_ACTIONS.keys()) == []
    assert sorted(TRIGGER_ACTIONS.keys() - triggers) == []


def test_each_transition_lists_the_machines_rows_and_actions_behind_it() -> None:
    graphs = {graph.key: graph for graph in build_state_machine_catalog()}
    lot = graphs["lot_status"]

    canceled = next(
        t for t in lot.transitions if t.trigger == "cancel_lot_request" and t.from_state == "draft"
    )

    assert canceled.to_state == "canceled"
    assert canceled.intent_text_keys == ("lot.cancel",)
    assert {r.text_key for r in lot.rules if "canceled" in r.results} == set(
        canceled.rule_text_keys
    )
    assert ("lot_position_status", "canceled") in {
        (i.machine, i.to_state) for i in canceled.implications
    }
    assert sum(len(g.transitions) for g in graphs.values()) == len(TRANSITIONS)


def test_a_cascade_row_names_no_action_and_no_implication() -> None:
    rows = [t for g in build_state_machine_catalog() for t in g.transitions]

    cascades = [t for t in rows if t.cascade]
    position_kind = [
        t
        for g in build_state_machine_catalog()
        if g.key == "lot_position_kind"
        for t in g.transitions
    ]

    assert cascades
    assert all(not t.intent_text_keys and not t.implications for t in cascades)
    # The kind and the status of a position are one aggregate.
    assert not any(t.cascade for t in position_kind if t.subject == "lot_position_status")
