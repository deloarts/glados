"""
Static guards for hexagonal layering. These are cheap AST-based checks that
run as part of the normal test suite (no extra tooling required) and fail
fast with a precise file:line if a forbidden import is introduced.

Kept intentionally narrow: only invariants that are easy to break in this
codebase are enforced here. Broader/whole-graph
layering is covered by `import-linter` (`poetry run lint-imports`,
configured in pyproject.toml under [tool.importlinter]), this file exists
so the same guarantees also show up in `pytest` output and in editors that
run tests but not standalone lint tools.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

from src.modules.fulfillment.application.services.lifecycle_reconciler import RECONCILED_AGGREGATES
from src.modules.fulfillment.domain.services.lifecycle.stored import LifecycleField
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"


def _layer_dirs(*parts: str) -> list[Path]:
    """The directory `parts` (such as `application/use_cases`) of every
    module, the shared kernel, the read tier and the composition root."""
    roots = [*sorted((SRC_ROOT / "modules").iterdir()), *(SRC_ROOT / t for t in _TIERS)]
    return [root.joinpath(*parts) for root in roots if root.joinpath(*parts).is_dir()]


_TIERS = ("shared_kernel", "read", "bootstrap")
_OUTER_LAYERS = ("application", "adapters", "infrastructure", "ports")


def _layer_modules(*layers: str) -> set[str]:
    """The dotted names of `layers` in every module and tier, for the
    forbidden module sets below."""
    return {
        ".".join(("src", *directory.relative_to(SRC_ROOT).parts))
        for layer in layers
        for directory in _layer_dirs(layer)
    }


DOMAIN_FORBIDDEN_MODULES = {
    *_layer_modules(*_OUTER_LAYERS),
    "src.read",
    "src.bootstrap",
    "fastapi",
    "starlette",
    "sqlalchemy",
    "pydantic",
    "pydantic_settings",
    "boto3",
    "botocore",
    "azure",
    "redis",
    "ldap3",
}

PORTS_FORBIDDEN_MODULES = _layer_modules("application", "adapters")


def _iter_py_files(package_dirs: Path | list[Path]) -> Iterator[Path]:
    for package_dir in package_dirs if isinstance(package_dirs, list) else [package_dirs]:
        for path in sorted(package_dir.rglob("*.py")):
            if "__pycache__" not in path.parts:
                yield path


def _imported_modules(file_path: Path) -> Iterator[tuple[int, str]]:
    """Yields (line_number, imported_module) for every import in the file."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif (
            isinstance(node, ast.ImportFrom) and node.module and node.level == 0
        ):  # skip relative imports (none expected here)
            yield node.lineno, node.module


def _violations(package_dirs: list[Path], forbidden_modules: set[str]) -> list[str]:
    violations = []
    for file_path in _iter_py_files(package_dirs):
        for lineno, module in _imported_modules(file_path):
            hit = any(module == f or module.startswith(f + ".") for f in forbidden_modules)
            if hit:
                rel = file_path.relative_to(SRC_ROOT.parent)
                violations.append(f"{rel}:{lineno} imports '{module}'")
    return violations


def test_domain_layer_has_no_framework_or_outer_layer_imports() -> None:
    """
    src/domain must be pure: no FastAPI/SQLAlchemy/Pydantic/boto3/etc., and no
    imports from application/adapters/infrastructure/ports. Business rules must
    not depend on how they're delivered or persisted.
    """
    violations = _violations(_layer_dirs("domain"), DOMAIN_FORBIDDEN_MODULES)
    assert not violations, "Domain layer purity violated:\n" + "\n".join(violations)


def test_ports_layer_does_not_depend_on_application_or_adapters() -> None:
    """
    src/ports defines the interfaces application and adapters both depend on.
    If a port imports from application or adapters, the dependency direction
    inverts and the port stops being a stable boundary. The *FilterDto types
    the port interfaces take therefore live in src/ports, not in
    application/dto.
    """
    violations = _violations(_layer_dirs("ports"), PORTS_FORBIDDEN_MODULES)
    assert not violations, "Ports layer independence violated:\n" + "\n".join(violations)


USE_CASES_ROOTS = _layer_dirs("application", "use_cases")

# Helpers in src/modules/platform/application/services/retry_on_conflict.py that commit the
# caller's unit of work on its behalf. They count as commits for the ordering
# rule below, otherwise a call site could sidestep it by using one.
COMMIT_HELPERS = {"commit_or_raise_numbering_conflict", "commit_with_number_retry"}


def _name_of(node: ast.AST) -> str:
    """The last name in an expression such as `self._uow` or `uow`."""
    if isinstance(node, ast.Attribute):
        return node.attr
    return getattr(node, "id", "")


def _is_unit_of_work_commit(node: ast.Call) -> bool:
    """A `.commit()` on anything named like a unit of work (`uow`, `_uow`,
    `self._unit_of_work`, `tx_uow`), or a call to a helper that commits
    one."""
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "commit":
        name = _name_of(func.value).lower()
        return "uow" in name or "unit_of_work" in name
    return isinstance(func, ast.Name) and func.id in COMMIT_HELPERS


def test_unit_of_work_commits_are_recognised_under_any_name() -> None:
    tree = ast.parse(
        "async def f(self, uow):\n"
        "    await self._uow.commit()\n"
        "    await uow.commit()\n"
        "    await self._unit_of_work.commit()\n"
        "    await commit_with_number_retry(self._uow)\n"
        "    await self._session.commit()\n"
    )
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert sorted(node.lineno for node in calls if _is_unit_of_work_commit(node)) == [2, 3, 4, 5]


def _publish_and_commit_lines(function: ast.AST) -> tuple[list[int], list[int]]:
    publishes: list[int] = []
    commits: list[int] = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "publish"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr.endswith("_bus")
        ):
            publishes.append(node.lineno)
        if _is_unit_of_work_commit(node):
            commits.append(node.lineno)
    return publishes, commits


def test_no_use_case_publishes_after_committing_its_unit_of_work() -> None:
    """
    Events go through the transactional outbox
    (src/modules/platform/adapters/outbound/persistence/event_outbox.py), which stages a row in
    the caller's own session. A row staged AFTER `uow.commit()` is never
    committed by anyone: `get_db()` only closes the session, it never commits,
    so the event is silently discarded.

    The rule is therefore: within one function body, no `_bus.publish()` may
    appear at a lexical position after a `_uow.commit()`. This is the static
    half of the guard; EVENT_OUTBOX_ABANDONED (change_tracking.py) is the
    runtime half.
    """
    violations = []
    for file_path in _iter_py_files(USE_CASES_ROOTS):
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            publishes, commits = _publish_and_commit_lines(node)
            if not publishes or not commits:
                continue
            first_commit = min(commits)
            for lineno in sorted(publishes):
                if lineno > first_commit:
                    rel = file_path.relative_to(SRC_ROOT.parent)
                    violations.append(
                        f"{rel}:{lineno} publishes after the commit at line {first_commit} "
                        f"(in {node.name}())"
                    )
    assert not violations, (
        "Event published after its unit of work committed (the staged outbox row "
        "would be discarded):\n" + "\n".join(violations)
    )


REPOSITORIES_ROOTS = _layer_dirs("adapters", "outbound", "persistence", "repositories")

# Repository functions allowed to commit on their own, as "relative/path.py:function".
# Every write belongs to the unit of work of the use case that makes it, so this
# stays empty. An entry needs a comment in the repository explaining why that write
# cannot join its caller's transaction; prefer giving the write its own use case
# and unit of work instead.
REPOSITORY_COMMIT_ALLOWLIST: set[str] = set()


def _commit_calls(tree: ast.AST) -> Iterator[tuple[int, str]]:
    """Yields (line_number, enclosing_function) for every `<x>.commit()` call."""
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "commit"
            ):
                yield node.lineno, function.name


def test_no_repository_commits() -> None:
    """
    Repositories only flush. The use case that writes owns an IUnitOfWork and
    commits it once, after its writes and after publishing its events on the
    transactional outbox, so the writes and their events land atomically. A
    repository that commits on its own splits that transaction: a later
    failure can no longer roll the earlier write back, and an event staged
    before the repository's commit would be committed with a write the use
    case has not finished.
    """
    violations = []
    for file_path in _iter_py_files(REPOSITORIES_ROOTS):
        root = next(root for root in REPOSITORIES_ROOTS if file_path.is_relative_to(root))
        rel = file_path.relative_to(root).as_posix()
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for lineno, function in _commit_calls(tree):
            if f"{rel}:{function}" in REPOSITORY_COMMIT_ALLOWLIST:
                continue
            violations.append(f"{file_path.relative_to(SRC_ROOT.parent)}:{lineno} in {function}()")
    assert not violations, (
        "Repository commits on its own instead of leaving the commit to the use "
        "case's unit of work:\n" + "\n".join(violations)
    )


def test_no_naive_datetime_stripping_in_src() -> None:
    """
    Every DateTime column is timezone-aware (`timestamptz`), so
    `datetime.now(UTC)` is always written and compared as-is. This guards
    against `.replace(tzinfo=None)` papering over a naive column type.
    """
    violations = []
    for file_path in _iter_py_files(SRC_ROOT):
        for lineno, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), 1):
            if "replace(tzinfo=None)" in line:
                rel = file_path.relative_to(SRC_ROOT.parent)
                violations.append(f"{rel}:{lineno} strips tzinfo from a datetime")
    assert not violations, "Naive-datetime stripping reintroduced:\n" + "\n".join(violations)


# ── Lifecycle statuses: one writer, reconciled before commit ─────────────

LIFECYCLE_DOMAIN_ROOTS = _layer_dirs("domain", "services", "lifecycle")

# Directories whose status and kind writes are no lifecycle derivation: the
# persistence mappers and repositories copy fields between entities and rows,
# and PDM ingest writes catalogue statuses and file and folder kinds.
STATUS_WRITE_EXEMPT_DIRS = (
    *(
        f"{directory.relative_to(SRC_ROOT.parent).as_posix()}/"
        for directory in _layer_dirs("adapters", "outbound", "persistence")
    ),
    "src/modules/external_data/application/use_cases/pdm/",
)

# Writes allowed by hand, keyed "path:function:target": the status of a catalogue
# item or a project is the user's intent and has nothing to derive it from.
INTENT_STATUS_WRITERS = {
    "src/modules/catalogue/application/use_cases/bought_item/update_bought_item.py:"
    "UpdateBoughtItem.execute._apply_and_save:item.status",
    "src/modules/catalogue/application/use_cases/made_item/create_made_item_revision.py:"
    "CreateMadeItemRevision._write_revision:source.status",
    "src/modules/catalogue/application/use_cases/made_item/update_made_item.py:"
    "UpdateMadeItem._apply_changes:target.status",
    "src/modules/catalogue/application/use_cases/source_item/update_source_item.py:"
    "UpdateSourceItem.execute:item.status",
    # A merge into the item its source had replaced undoes the replacement.
    "src/modules/catalogue/application/use_cases/bought_item/merge_bought_item.py:"
    "MergeBoughtItem.execute:target.status",
    "src/modules/catalogue/application/use_cases/made_item/merge_made_item.py:MergeMadeItem.execute:target.status",
    "src/modules/workspace/application/use_cases/project/delete_project.py:DeleteProject.execute:project.status",
    "src/modules/workspace/application/use_cases/project/update_project.py:"
    "UpdateProject._apply_changes:project.status",
    # A terminal's status records what an admin or the device sign-in did
    # (approve, revoke, sign in again); it is no lifecycle status.
    "src/modules/operations/domain/services/terminal_rules.py:approve:terminal.status",
    "src/modules/operations/domain/services/terminal_rules.py:revoke:terminal.status",
    "src/modules/operations/domain/services/terminal_rules.py:return_to_pending:terminal.status",
}

# Writes of a field named like a derived one that the reconciler does not
# own on that row, keyed "path:function:target". An order line's delivery
# date and ordered date record its own arrivals and its ordered intent; the
# reconciler derives those two fields only on the order.
FACT_FIELD_WRITERS = {
    "src/modules/fulfillment/application/use_cases/order/correct_order_item_delivery.py:"
    "CorrectOrderItemDelivery.execute:item.delivery_date",
    "src/modules/fulfillment/domain/services/delivery_booking_rules.py:"
    "record_delivery_on_line:line.delivery_date",
    "src/modules/fulfillment/application/use_cases/order/mark_order_item_ordered.py:record_ordered:item.ordered_date",
    # Submitting an order records its placed intent; the reconciler stamps
    # the date only for an order whose lines were ordered one by one.
    "src/modules/fulfillment/application/use_cases/order/update_order.py:SubmitOrder.execute:order.ordered_date",
    # A copy of a position for a read-only view of pieces accepted earlier
    # in the same transaction; nothing saves it.
    "src/modules/fulfillment/domain/services/delivery_booking_rules.py:"
    "_with_accepted:position.quantity_completed",
    # Shrinking a lot for scrap keeps each position's completed count within
    # its lowered quantity, as the database requires before the flush; the
    # reconciler derives the same value from the completion rows.
    "src/modules/fulfillment/domain/services/lot_rules.py:shrink_lot_for_scrap:lot_position.quantity_completed",
}

_ORDER_USE_CASES = "src/modules/fulfillment/application/use_cases/order/"
_LOT_USE_CASES = "src/modules/fulfillment/application/use_cases/production_lot/"
_PRODUCTION_ORDER_USE_CASES = "src/modules/fulfillment/application/use_cases/production_order/"

# Status and kind writers allowed outside the lifecycle domain, by the
# aggregate they write. Every set is empty: the lifecycle reconciler is the
# only writer of these aggregates' statuses, so a hand-written status or kind
# fails the guard below, and an aggregate in RECONCILED_AGGREGATES may never
# gain an entry here.
PRE_RECONCILER_STATUS_WRITERS: dict[LifecycleAggregate, set[str]] = {
    LifecycleAggregate.ORDER_ITEMS: set(),
    LifecycleAggregate.ORDERS: set(),
    LifecycleAggregate.PRODUCTION_ORDERS: set(),
    LifecycleAggregate.LOT_POSITIONS: set(),
    LifecycleAggregate.LOTS: set(),
    LifecycleAggregate.BOUGHT_DEMANDS: set(),
    LifecycleAggregate.MADE_DEMANDS: set(),
    LifecycleAggregate.SOURCE_DEMANDS: set(),
    LifecycleAggregate.QUOTE_REQUESTS: set(),
}


def _scoped_nodes(tree: ast.AST) -> Iterator[tuple[str, ast.AST]]:
    """Yields (enclosing qualified name, node) for every node below the
    module, the name joined from the classes and functions around it. A
    function or class is yielded with the scope it is defined in."""

    def visit(node: ast.AST, scope: list[str]) -> Iterator[tuple[str, ast.AST]]:
        for child in ast.iter_child_nodes(node):
            yield ".".join(scope) or "<module>", child
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                yield from visit(child, [*scope, child.name])
            else:
                yield from visit(child, scope)

    yield from visit(tree, [])


def _is_constructor_own_attribute(scope: str, attribute: ast.Attribute) -> bool:
    """An object setting its own attribute in its constructor, such as a
    filter object's `self.status = status`, decides no lifecycle status. The
    same write in any other method does."""
    own = isinstance(attribute.value, ast.Name) and attribute.value.id == "self"
    return own and scope.split(".")[-1] == "__init__"


# Every field the lifecycle reconciler derives and stores: status and kind,
# and the stamps and counts that follow them (completed counts, completed_at,
# actual_end, delivery_date, ordered_date, the canceled flag).
LIFECYCLE_FIELDS = frozenset(field.value for field in LifecycleField)


def _lifecycle_attribute_writes(file_path: Path) -> Iterator[str]:
    """Yields "function:target" for every assignment to an attribute named
    like a lifecycle field, except an object setting its own attribute in
    its constructor."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    for scope, node in _scoped_nodes(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AugAssign | ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for target in targets:
            for sub in ast.walk(target):
                if (
                    isinstance(sub, ast.Attribute)
                    and sub.attr in LIFECYCLE_FIELDS
                    and isinstance(sub.ctx, ast.Store)
                    and not _is_constructor_own_attribute(scope, sub)
                ):
                    yield f"{scope}:{ast.unparse(sub)}"


def test_a_method_setting_its_own_status_is_a_status_writer(tmp_path: Path) -> None:
    """Only a constructor may set its own `status` unnoticed: an entity
    method that writes `self.status` decides a status by hand like any other
    writer, so the status-writer test must see it."""
    module = tmp_path / "entity.py"
    module.write_text(
        "class Lot:\n"
        "    def __init__(self, status):\n"
        "        self.status = status\n"
        "    def put_on_hold(self):\n"
        "        self.status = 'on_hold'\n"
        "        self.kind: str = 'external'\n"
        "    def mark(self, other):\n"
        "        other.status = 'done'\n",
        encoding="utf-8",
    )

    assert sorted(_lifecycle_attribute_writes(module)) == [
        "Lot.mark:other.status",
        "Lot.put_on_hold:self.kind",
        "Lot.put_on_hold:self.status",
    ]


def _status_writes_outside_the_lifecycle_domain() -> set[str]:
    writes: set[str] = set()
    for file_path in _iter_py_files(SRC_ROOT):
        rel = file_path.relative_to(SRC_ROOT.parent).as_posix()
        if any(file_path.is_relative_to(root) for root in LIFECYCLE_DOMAIN_ROOTS) or rel.startswith(
            STATUS_WRITE_EXEMPT_DIRS
        ):
            continue
        writes.update(f"{rel}:{write}" for write in _lifecycle_attribute_writes(file_path))
    return writes


def test_status_written_only_by_lifecycle_domain() -> None:
    """
    A lifecycle status or kind, and the counts and stamps that follow it, are
    derived from facts and intents (src/domain/services/lifecycle/), and
    lifecycle/stored.py writes the derived value back for the lifecycle
    reconciler. Any other assignment to an attribute named like one of
    those fields decides it by hand and spreads the rules over several
    places, so it fails unless PRE_RECONCILER_STATUS_WRITERS,
    INTENT_STATUS_WRITERS or FACT_FIELD_WRITERS lists it. An allowlist entry
    whose write is gone fails as stale too, so the lists hold only writes
    that exist.
    """
    writes = _status_writes_outside_the_lifecycle_domain()
    pre_reconciler = set().union(*PRE_RECONCILER_STATUS_WRITERS.values())
    allowed = INTENT_STATUS_WRITERS | FACT_FIELD_WRITERS | pre_reconciler
    unexpected = sorted(writes - allowed)
    stale = sorted(allowed - writes)
    assert not unexpected, (
        "Lifecycle field written outside the lifecycle domain package; record the facts "
        "and intents and let the lifecycle reconciler store the status:\n" + "\n".join(unexpected)
    )
    assert not stale, "Allowlist entries whose write is gone, remove them:\n" + "\n".join(stale)


def test_reconciled_aggregates_have_no_pre_reconciler_status_writer() -> None:
    """
    An aggregate the reconciler writes must have no other status writer left,
    or the two would overwrite each other, and the other writer would not
    keep the intents the reconciler derives from.
    """
    still_written = {
        aggregate.value: sorted(entries)
        for aggregate, entries in PRE_RECONCILER_STATUS_WRITERS.items()
        if aggregate in RECONCILED_AGGREGATES and entries
    }
    assert not still_written, f"Reconciled aggregates still written by hand: {still_written}"


APPLICATION_ROOTS = _layer_dirs("application")

# Use case packages whose committing functions must reconcile or be listed
# below. Any other module under src/application joins them as soon as it
# imports a repository of a reconciled aggregate.
LIFECYCLE_USE_CASE_PACKAGES = (
    "_demand_family",
    "order",
    "production_lot",
    "production_order",
    "bought_item_demand",
    "made_item_demand",
    "source_item_demand",
    "source_item_allocation",
    "quote_request",
)

# Port modules and repository ports of the reconciled aggregates. A module
# that imports one can write a lifecycle fact, so its commits are checked.
LIFECYCLE_PORT_MODULES = frozenset(
    {
        "order_repository",
        "production_lot_repository",
        "production_order_repository",
        "made_item_demand_repository",
        "source_item_demand_repository",
        "quote_request_repository",
    }
)
LIFECYCLE_PORT_NAMES = frozenset(
    {"IBoughtItemDemandItemRepository", "IBoughtItemAllocationRepository"}
)

# Committing functions of those modules, keyed "path:function", that record
# no lifecycle fact or intent, so they have nothing to reconcile.
NON_LIFECYCLE_COMMITS = {
    # Files, thumbnails and catalogue rows.
    "src/modules/fulfillment/application/use_cases/order/delete_order_file.py:DeleteOrderFile.execute",
    "src/modules/fulfillment/application/use_cases/production_order/delete_production_order_file.py:"
    "DeleteProductionOrderFile.execute",
    "src/modules/fulfillment/application/use_cases/production_order/download_production_order_file.py:"
    "DownloadProductionOrderFile.execute",
    "src/modules/fulfillment/application/use_cases/production_order/update_production_order_file.py:"
    "UpdateProductionOrderFile.execute",
    # Display buckets.
    "src/modules/fulfillment/application/use_cases/bought_item_demand/set_demand_item_bucket.py:SetDemandItemBucket.execute",
    "src/modules/fulfillment/application/use_cases/made_item_demand/set_demand_item_bucket.py:"
    "SetDemandItemBucket.execute",
    "src/modules/fulfillment/application/use_cases/source_item_demand/set_demand_item_bucket.py:"
    "SetDemandItemBucket.execute",
    # Fields no derivation reads: notes, dates, suppliers, machines, queue
    # places, priorities, durations, assessments, time budgets, operators.
    "src/modules/fulfillment/application/use_cases/order/create_order.py:CreateOrder.execute",
    "src/modules/fulfillment/application/use_cases/order/update_order.py:UpdateOrder.execute",
    "src/modules/fulfillment/application/use_cases/order/set_order_extra_costs.py:SetOrderExtraCosts.execute",
    "src/modules/fulfillment/application/use_cases/order/set_order_supplier_order_numbers.py:"
    "SetOrderSupplierOrderNumbers.execute",
    "src/modules/fulfillment/application/use_cases/order/mark_order_item_ready_for_pickup.py:"
    "MarkOrderItemReadyForPickup.execute",
    "src/modules/fulfillment/application/use_cases/production_order/production_order_lifecycle.py:"
    "_ProductionOrderLifecycleBase._recompute_time_budget_if_needed",
    "src/modules/fulfillment/application/use_cases/production_order/reassign_production_order_machine.py:"
    "ReassignProductionOrderMachine.execute",
    "src/modules/fulfillment/application/use_cases/production_order/record_manufacturing_assessment.py:"
    "RecordManufacturingAssessment.execute",
    "src/modules/fulfillment/application/use_cases/production_order/reorder_production_orders.py:"
    "ReorderProductionOrders.execute",
    "src/modules/fulfillment/application/use_cases/production_order/update_production_order.py:"
    "UpdateProductionOrder.execute",
    # Lot step estimates and notes, the duration snapshots and time budgets
    # they feed, provisions and a rejected material source.
    "src/modules/fulfillment/application/use_cases/production_lot/lot_steps.py:UpdateLotStep.execute",
    "src/modules/fulfillment/application/use_cases/production_lot/replace_structure.py:ReplaceLotStructure.execute",
    "src/modules/fulfillment/application/use_cases/production_lot/record_lot_position_provision.py:"
    "RecordLotPositionProvision.execute",
    "src/modules/fulfillment/application/use_cases/production_lot/reject_lot_source.py:RejectLotSource.execute",
    # Deleting a demand, which is refused while it holds an allocation, so
    # nothing the reconciler derives reads the deleted row.
    "src/modules/fulfillment/application/use_cases/_demand_family/delete_demand.py:DeleteDemand.execute",
    # The source approval setting resets the approval of open lots, which
    # only gates the approve and reject actions; no derivation reads it.
    "src/modules/fulfillment/application/use_cases/admin_settings/update_production_settings.py:"
    "UpdateProductionSettings.execute",
    # Archiving a machine, refused while it holds live orders.
    "src/modules/fulfillment/application/use_cases/production_machine/archive_machine.py:"
    "ArchiveProductionMachine.execute",
    # The schedule walk writes planned windows and forecasts only.
    "src/modules/fulfillment/application/use_cases/production_schedule/recompute_machine_schedule.py:"
    "RecomputeMachineSchedule._walk_and_persist",
    "src/modules/fulfillment/application/use_cases/production_schedule/recompute_machine_schedule.py:"
    "RecomputeMachineSchedule.execute_all",
}

# Committing functions allowed to record lifecycle facts or intents without
# running the reconciler. The set is empty, so every such function must
# reconcile before it commits.
PRE_RECONCILER_COMMITS: set[str] = set()


def _is_reconciler_run(node: ast.Call) -> bool:
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "run"
        and _name_of(func.value).endswith("reconciler")
    )


def _registers_touches(node: ast.Call) -> bool:
    """A `touch_*` call on the reconciler, or a call that hands the
    reconciler to a helper, which registers the rows it locks."""
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr.startswith("touch"):
        return True
    arguments = [*node.args, *(keyword.value for keyword in node.keywords)]
    return any(_name_of(argument).endswith("reconciler") for argument in arguments)


class _ModuleCalls:
    """Resolves the helpers a function calls within its own module: methods
    of its class and of base classes defined there, and module functions."""

    def __init__(self, tree: ast.Module) -> None:
        self._functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        self._classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}

    def methods_of(self, class_name: str) -> dict[str, ast.AST]:
        methods: dict[str, ast.AST] = {}
        pending = [class_name]
        while pending:
            cls = self._classes.get(pending.pop(0))
            if cls is None:
                continue
            for node in cls.body:
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    methods.setdefault(node.name, node)
            pending += [base.id for base in cls.bases if isinstance(base, ast.Name)]
        return methods

    def callee(self, node: ast.Call, methods: dict[str, ast.AST]) -> ast.AST | None:
        func = node.func
        if isinstance(func, ast.Attribute) and _name_of(func.value) in {"self", "cls"}:
            return methods.get(func.attr)
        if isinstance(func, ast.Name):
            return self._functions.get(func.id)
        return None


def _touch_lines(
    function: ast.AST, calls: _ModuleCalls, methods: dict[str, ast.AST], seen: set[int]
) -> list[int]:
    """The lines in `function` that register touches, directly or through a
    helper of the same module that does."""
    lines: list[int] = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if _registers_touches(node):
            lines.append(node.lineno)
            continue
        helper = calls.callee(node, methods)
        if helper is not None and id(helper) not in seen:
            seen.add(id(helper))
            if _touch_lines(helper, calls, methods, seen):
                lines.append(node.lineno)
    return lines


def _imports_a_lifecycle_port(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.rsplit(".", 1)[-1] in LIFECYCLE_PORT_MODULES:
                return True
            if any(alias.name in LIFECYCLE_PORT_NAMES for alias in node.names):
                return True
    return False


def _commit_order_violations(function: ast.AST) -> tuple[list[int], bool]:
    """The commits of `function` without a reconciler run since the previous
    commit, and whether it commits at all."""
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
    runs = sorted(node.lineno for node in calls if _is_reconciler_run(node))
    commits = sorted(node.lineno for node in calls if _is_unit_of_work_commit(node))
    unreconciled: list[int] = []
    previous = 0
    for commit in commits:
        if not any(previous < run < commit for run in runs):
            unreconciled.append(commit)
        previous = commit
    return unreconciled, bool(commits)


def _lifecycle_modules() -> Iterator[tuple[str, ast.Module]]:
    """Every module under src/application whose commits are checked: the
    lifecycle use case packages, and any module importing a repository of a
    reconciled aggregate."""
    packages = tuple(
        f"{root.relative_to(SRC_ROOT.parent).as_posix()}/{name}/"
        for root in USE_CASES_ROOTS
        for name in LIFECYCLE_USE_CASE_PACKAGES
        if (root / name).is_dir()
    )
    for file_path in _iter_py_files(APPLICATION_ROOTS):
        rel = file_path.relative_to(SRC_ROOT.parent).as_posix()
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        if rel.startswith(packages) or _imports_a_lifecycle_port(tree):
            yield rel, tree


def _reconcile_violations(rel: str, tree: ast.Module, allowed: set[str]) -> Iterator[str]:
    """Yields "key" for an allowlisted function that does not reconcile, and
    a message for every other violation in the module."""
    calls = _ModuleCalls(tree)
    for scope, node in _scoped_nodes(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        key = f"{rel}:{node.name if scope == '<module>' else f'{scope}.{node.name}'}"
        methods = calls.methods_of(scope.split(".")[0]) if scope != "<module>" else {}
        unreconciled, commits = _commit_order_violations(node)
        if commits and key in allowed and unreconciled:
            yield key
        elif unreconciled:
            yield f"{key} commits at line {unreconciled[0]} without a reconciler run before it"
        touches = _touch_lines(node, calls, methods, {id(node)})
        for call in ast.walk(node):
            if (
                isinstance(call, ast.Call)
                and _is_reconciler_run(call)
                and not any(line < call.lineno for line in touches)
            ):
                yield f"{key} runs the reconciler at line {call.lineno} with nothing touched"


def test_lifecycle_use_cases_reconcile_before_commit() -> None:
    """
    A use case that records lifecycle facts or intents registers what it
    touched (a `touch_*` call, or handing the reconciler to a helper that
    locks for it) and calls `<...>reconciler.run(...)` before every commit
    of its unit of work, so the derived statuses and their events commit
    with the facts; a run with nothing touched derives nothing. The scan
    covers the lifecycle use case packages and every module under
    src/application that imports a repository of a reconciled aggregate.
    Functions that record no lifecycle fact are listed in
    NON_LIFECYCLE_COMMITS, and PRE_RECONCILER_COMMITS lists those allowed to
    commit without reconciling; an entry that no longer commits, no longer
    exists or already reconciles fails as stale.
    """
    allowed = NON_LIFECYCLE_COMMITS | PRE_RECONCILER_COMMITS
    violations: list[str] = []
    listed_and_seen: set[str] = set()
    for rel, tree in _lifecycle_modules():
        for finding in _reconcile_violations(rel, tree, allowed):
            if finding in allowed:
                listed_and_seen.add(finding)
            else:
                violations.append(finding)
    stale = sorted(allowed - listed_and_seen)
    assert not violations, (
        "Lifecycle use case commits without registering and running the lifecycle "
        "reconciler first:\n" + "\n".join(violations)
    )
    assert not stale, "Allowlist entries that are gone or reconcile, remove them:\n" + "\n".join(
        stale
    )


def test_a_second_commit_and_an_untouched_run_are_reconcile_violations() -> None:
    tree = ast.parse(
        "class Uc:\n"
        "    async def execute(self):\n"
        "        self._reconciler.touch_orders([1])\n"
        "        await self._reconciler.run(a, n)\n"
        "        await self._uow.commit()\n"
        "        await self._uow.commit()\n"
        "    async def bare(self):\n"
        "        await self._reconciler.run(a, n)\n"
        "        await self._uow.commit()\n"
        "    async def helped(self):\n"
        "        await self._lock()\n"
        "        await self._reconciler.run(a, n)\n"
        "        await self._uow.commit()\n"
        "    async def _lock(self):\n"
        "        await lock_rows(self._reconciler, [1])\n"
    )
    assert list(_reconcile_violations("m.py", tree, set())) == [
        "m.py:Uc.execute commits at line 6 without a reconciler run before it",
        "m.py:Uc.bare runs the reconciler at line 8 with nothing touched",
    ]


PERSISTENCE_ROOTS = _layer_dirs("adapters", "outbound", "persistence")

# ORM models of the reconciled aggregates. A Core UPDATE on one of them
# bypasses the entity, so it may not name a lifecycle field.
LIFECYCLE_ORM_MODELS = frozenset(
    {
        "OrderOrmModel",
        "OrderItemOrmModel",
        "ProductionLotOrmModel",
        "LotPositionOrmModel",
        "ProductionOrderOrmModel",
        "BoughtItemDemandItemOrmModel",
        "MadeItemDemandItemOrmModel",
        "SourceItemDemandItemOrmModel",
        "QuoteRequestOrmModel",
    }
)

# The reconciler's bulk writer: it writes the values the reconciler derived
# onto any model through a column map, so it names no field itself.
CORE_LIFECYCLE_WRITERS = frozenset(
    {"src/modules/platform/adapters/outbound/persistence/grouped_attribute_writes.py"}
)


def _updated_model(values_call: ast.Call) -> str:
    """The model of the `update(Model)` a `.values(...)` call chains onto,
    or "" when the chain starts elsewhere."""
    node: ast.AST = values_call.func
    while isinstance(node, ast.Attribute | ast.Call):
        if isinstance(node, ast.Call):
            if _name_of(node.func) == "update" and node.args:
                return _name_of(node.args[0])
            node = node.func
        else:
            node = node.value
    return ""


def _named_values(values_call: ast.Call) -> set[str]:
    """The column names a `.values(...)` call sets by keyword or by a
    literal key of a dict argument."""
    names = {keyword.arg for keyword in values_call.keywords if keyword.arg}
    for argument in values_call.args:
        if isinstance(argument, ast.Dict):
            names |= {
                key.value
                for key in argument.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
    return names


def _core_lifecycle_field_updates(file_path: Path) -> Iterator[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "values"
        ):
            model = _updated_model(node)
            fields = sorted(_named_values(node) & LIFECYCLE_FIELDS)
            if model in LIFECYCLE_ORM_MODELS and fields:
                yield f"{node.lineno} update({model}) sets {', '.join(fields)}"


def test_core_update_on_a_lifecycle_model_names_no_lifecycle_field(tmp_path: Path) -> None:
    module = tmp_path / "repo.py"
    module.write_text(
        "async def f(db):\n"
        "    await db.execute(sa.update(ProductionLotOrmModel).where(x).values(status='x'))\n"
        "    await db.execute(update(OrderOrmModel).values({'delivery_date': None}))\n"
        "    await db.execute(update(OrderOrmModel).values(notes='n'))\n"
        "    await db.execute(update(BackupRunOrmModel).values(status='done'))\n",
        encoding="utf-8",
    )
    assert list(_core_lifecycle_field_updates(module)) == [
        "2 update(ProductionLotOrmModel) sets status",
        "3 update(OrderOrmModel) sets delivery_date",
    ]


def test_no_core_update_writes_a_lifecycle_field() -> None:
    """
    A Core `update(Model).values(...)` skips the entity, its version check
    and the reconciler, so on a reconciled aggregate's model it may not set
    a lifecycle field; only the reconciler's bulk writer does that.
    """
    violations = [
        f"{file_path.relative_to(SRC_ROOT.parent)}:{finding}"
        for file_path in _iter_py_files(PERSISTENCE_ROOTS)
        if file_path.relative_to(SRC_ROOT.parent).as_posix() not in CORE_LIFECYCLE_WRITERS
        for finding in _core_lifecycle_field_updates(file_path)
    ]
    assert not violations, (
        "Core UPDATE sets a lifecycle field outside the reconciler's writer:\n"
        + "\n".join(violations)
    )


def test_every_source_directory_is_a_package() -> None:
    """import-linter only sees modules inside packages, so a directory of
    Python files without an __init__.py drops out of every contract."""
    missing = sorted(
        str(directory.relative_to(SRC_ROOT))
        for directory in {path.parent for path in SRC_ROOT.rglob("*.py")}
        if "__pycache__" not in directory.parts and not (directory / "__init__.py").exists()
    )
    assert missing == [], f"Add an __init__.py to: {missing}"
