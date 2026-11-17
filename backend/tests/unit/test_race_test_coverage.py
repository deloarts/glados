"""
Every use case that writes lifecycle rows, which is every one that runs the
lifecycle reconciler, either has a race test on Postgres in tests/pg or an
explicit exemption here that says why it needs none. A use case counts as
race-tested when a tests/pg module builds it, or a subclass of it, through
its dependency getter. A new writer therefore fails this test until it gets
one or the other, and an exemption that a race test has made unneeded, or
that names a use case that no longer exists, fails it as well.
"""

import ast
import importlib
import re
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2]
_USE_CASES = sorted(_BACKEND.glob("src/modules/*/application/use_cases"))
_DEPS = sorted(_BACKEND.glob("src/modules/*/adapters/inbound/api/deps/*.py"))
_RACE_TESTS = _BACKEND / "tests" / "pg"

# Lock families: a writer that takes the same locks, in the same order and
# through the same lock plan as a race-tested writer of its family, is
# serialized by the same mechanism the race test proves.
_ORDER_LINE = (
    "locks its line with the line's order through the lock plan like "
    "ProcessOrderItemDelivery and MoveOrderItem, whose races are tested"
)
_ORDER = "locks the order and then its lines like CancelOrder, whose race is tested"
_LOT = "locks the lot first and then its work like HoldLot, whose race is tested"
_PRODUCTION_ORDER = (
    "locks the lot and then the production order like StartProductionOrder and "
    "PauseProductionOrder, whose races are tested"
)
_DEMAND = (
    "locks the demand through the lock plan like CreateAllocation and CreateDemandItem, "
    "whose races are tested"
)

EXEMPT: dict[str, str] = {
    "AutoAllocateOnOrderLines": _DEMAND,
    "CommitBatchDemands": _DEMAND,
    "FulfillFromStock": _DEMAND,
    "UpdateDemand": _DEMAND,
    "UpdateDemandStatus": _DEMAND,
    "CancelDemandItem": _DEMAND,
    "CancelMadeItemDemand": _DEMAND,
    "CancelSourceItemDemand": _DEMAND,
    "CreateSourceItemDemand": _DEMAND,
    "UpdateSourceItemDemand": _DEMAND,
    "CancelOrderItem": _ORDER_LINE,
    "CloseOrderItemShort": _ORDER_LINE,
    "CorrectOrderItemDelivery": _ORDER_LINE,
    "RemoveOrderItem": _ORDER_LINE,
    "MarkOrderItemOrdered": _ORDER_LINE,
    "MarkAllOrderItemsOrdered": _ORDER,
    "MarkOrderItemRequested": _ORDER_LINE,
    "MarkAllOrderItemsRequested": _ORDER,
    "ReopenOrderItem": _ORDER_LINE,
    "RequestOrder": _ORDER,
    "UpdateOrderItem": _ORDER_LINE,
    "ApproveLotSource": _LOT,
    "AssignExternalPosition": _LOT,
    "UnassignExternalPosition": _LOT,
    "AutoAssignLots": (
        "creates new lots for demands under the sweep lock, which the unit tests of the "
        "sweep cover; it never writes a row another request holds"
    ),
    "CreateLot": (
        "writes a new lot and links demands through the demand locks like CreateAllocation, "
        "whose race is tested"
    ),
    "CancelLot": _LOT,
    "CompleteLot": _LOT,
    "ResumeLot": _LOT,
    "RegroupLotPositions": _LOT,
    "AppendLotPosition": _LOT,
    "AddLotStep": _LOT,
    "DeleteLotStep": _LOT,
    "ReorderLotSteps": _LOT,
    "ReplaceLotStructure": _LOT,
    "SwitchLotMaterialSource": _LOT,
    "MergeProductionOrders": _PRODUCTION_ORDER,
    "_QuoteRequestWriter": (
        "locks the request row before it reads it and takes no other lifecycle lock, so two "
        "writers of one request run one after the other on that row, which the award's race "
        "test locks last in the lock order"
    ),
}


def _class_of(module_path: Path, name: str) -> type:
    module = ".".join(module_path.relative_to(_BACKEND).with_suffix("").parts)
    cls: type = getattr(importlib.import_module(module), name)
    return cls


def _lifecycle_writers() -> dict[str, type]:
    """Every use case class whose own code runs the lifecycle reconciler."""
    writers: dict[str, type] = {}
    for path in sorted(p for root in _USE_CASES for p in root.rglob("*.py")):
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.ClassDef) and "reconciler.run(" in ast.unparse(node):
                writers[node.name] = _class_of(path, node.name)
    return writers


def _race_tested_classes() -> list[type]:
    """The use case classes tests/pg builds through their dependency getters."""
    returns: dict[str, tuple[Path, str]] = {}
    for path in _DEPS:
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.FunctionDef) and isinstance(node.returns, ast.Name):
                returns[node.name] = (path, node.returns.id)
    used = {
        name
        for path in _RACE_TESTS.glob("*.py")
        for name in re.findall(r"\b(get_\w+)\b", path.read_text())
    }
    classes = []
    for getter in sorted(used & returns.keys()):
        path, name = returns[getter]
        module = importlib.import_module(".".join(path.relative_to(_BACKEND).with_suffix("").parts))
        found = getattr(module, name, None)
        if isinstance(found, type):
            classes.append(found)
    return classes


def _covered(writer: type, tested: list[type]) -> bool:
    return any(issubclass(cls, writer) for cls in tested)


def test_every_lifecycle_writer_is_race_tested_or_exempt() -> None:
    writers = _lifecycle_writers()
    tested = _race_tested_classes()

    missing = sorted(
        name for name, cls in writers.items() if not _covered(cls, tested) and name not in EXEMPT
    )

    assert not missing, (
        f"lifecycle writers without a tests/pg race test or an exemption in this module: {missing}"
    )


def test_no_exemption_is_stale() -> None:
    writers = _lifecycle_writers()
    tested = _race_tested_classes()

    unknown = sorted(name for name in EXEMPT if name not in writers)
    covered = sorted(name for name in EXEMPT if name in writers and _covered(writers[name], tested))

    assert not unknown, f"exemptions for use cases that run no reconciler: {unknown}"
    assert not covered, f"exemptions for use cases a race test now covers: {covered}"
