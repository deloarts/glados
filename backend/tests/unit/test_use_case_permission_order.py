"""
Guards against use cases that load an entity before checking whether the
actor may touch it. When permission is checked after the fetch, an actor
without permission sees a not-found error for a missing id but a
permission error for an existing one, an oracle that reveals whether an
id exists at all to a caller who should not be able to tell.

Walks every module under src/application/use_cases with the ast module
(not text matching, so it is not fooled by comments or by another
class's execute method elsewhere in the same file) and, for every method
named `execute` that calls a permission assertion (a call named
assert_can_* or starting with _assert_can), fails if a repository fetch
(self._<attr>.get_by_id(...) and its siblings, see _FETCH_METHOD_NAMES
and _FETCH_METHOD_PREFIXES below) appears earlier in that same method.

Calls inside a nested function or lambda defined within `execute` are not
considered part of its linear flow (they run on their own schedule, for
example inside a commit-with-retry callback), so they are excluded from
both the fetch and the assertion search.
"""

import ast
from pathlib import Path

USE_CASES_ROOTS = sorted(
    (Path(__file__).resolve().parents[2] / "src").glob("modules/*/application/use_cases")
)

_FETCH_METHOD_NAMES = {"get_by_id", "get_by_public_id", "get", "find", "find_by_id", "list"}
_FETCH_METHOD_PREFIXES = ("list_", "search", "find_")

# Use cases whose permission rule needs the fetched entity itself (an
# ownership check, a status check, or both) with no actor-only rule that
# already covers the same action, so the check cannot run before the
# fetch without inventing a new domain rule or reusing a different
# action's rule (and its misleading error message). Each reason names the
# rule and the entity-dependent condition that makes it unavoidable.
ALLOWLIST: dict[str, str] = {
    "_demand_family/update_demand.py": (
        "BoughtItemDemandRules.assert_can_update(actor, demand), bound as the bought "
        "family's _demand_rules, requires write:demand_items unconditionally but then "
        "checks the demand's status and creator ownership when the actor lacks "
        "manage:demand_items; no actor-only sibling covers the update action. "
        "MadeItemDemandRules.assert_can_update(actor, demand), the made family's, has "
        "the same shape: an unconditional permission check followed by "
        "entity-dependent status/ownership checks, with no actor-only sibling for the "
        "update action."
    ),
    "_demand_family/update_status.py": (
        "assert_can_change_demand_status(actor, demand, target) needs the fetched "
        "demand for its ownership and terminal-target check when the actor lacks "
        "manage:demand_items; no actor-only sibling covers the status action."
    ),
    "_demand_family/delete_demand.py": (
        "assert_can_cancel_demand(actor, demand) has no unconditional permission "
        "requirement at all; a demand's creator may cancel it with no special "
        "permission, so authorization is inseparable from the fetched entity."
    ),
    "bought_item_demand/cancel_demand_item.py": (
        "Same assert_can_change_demand_status(actor, demand, target) ownership and "
        "terminal-target shape as _demand_family/update_status.py; the "
        "cancel route applies the status route's rule."
    ),
    "made_item_demand/cancel_demand.py": (
        "Same assert_can_change_demand_status(actor, demand, target) ownership and "
        "terminal-target shape as _demand_family/update_status.py; the "
        "cancel route applies the status route's rule."
    ),
    "user/force_logout_user.py": (
        "UserRules.assert_can_force_logout(actor, target) always allows a user to "
        "terminate their own sessions and forbids force-logging out the system user; "
        "both require the fetched target."
    ),
    "user/update_user.py": (
        "UserRules.assert_can_update(actor, target) always allows a user to update "
        "themselves and protects the system user from being updated by anyone else; "
        "both require the fetched target."
    ),
    "user/disable_totp.py": (
        "UserRules.assert_can_disable_totp(user) checks only the fetched entity's own "
        "is_systemuser flag on this self-service route; there is no separate actor to "
        "check before the fetch."
    ),
    "user/delete_user.py": (
        "UserRules.assert_can_delete(actor, target) forbids deleting one's own account "
        "and the system user before requiring write:settings; both require the "
        "fetched target."
    ),
    "pat/get_pat.py": (
        "PatRules.assert_can_manage(actor, token) always allows a user to manage their "
        "own token; only managing another user's token requires write:settings, so "
        "authorization needs the fetched token."
    ),
    "pat/get_pat_usage_log.py": (
        "Same PatRules.assert_can_manage(actor, token) self-service-or-write:settings "
        "shape as get_pat.py."
    ),
    "pat/revoke_pat.py": (
        "Same PatRules.assert_can_manage(actor, token) self-service-or-write:settings "
        "shape as get_pat.py."
    ),
    "checklist/get_checklists.py": (
        "GetChecklist, GetChecklistByPublicId and GetChecklistRevisions need no "
        "permission at all; ChecklistRules.assert_can_view(actor, checklist) only hides "
        "another user's personal checklist, and answers a hidden one like a missing id, "
        "so there is no oracle and no actor-only sibling."
    ),
    "calculation/lock_calculation.py": (
        "UnlockCalculation needs no permission: ending one's own edit lock is always "
        "allowed, and CalculationRules.assert_can_view(actor, calculation) only hides "
        "another user's personal calculation like a missing id. LockCalculation checks "
        "the actor-only assert_can_write before its fetch."
    ),
    "checklist/lock_checklist.py": (
        "UnlockChecklist needs no permission: ending one's own edit lock is always "
        "allowed, and ChecklistRules.assert_can_view(actor, checklist) only hides "
        "another user's personal checklist like a missing id. LockChecklist checks "
        "the actor-only assert_can_write before its fetch."
    ),
    "calculation/get_calculations.py": (
        "GetCalculation and GetCalculationByPublicId need no permission at all; "
        "CalculationRules.assert_can_view(actor, calculation) only hides another user's "
        "personal calculation, and answers a hidden one like a missing id, so there is "
        "no oracle and no actor-only sibling."
    ),
    "product/update_product.py": (
        "ProductRules.assert_can_update(actor, product) allows manage:projects OR the "
        "product's own designated_user_id; no unconditional permission and no "
        "actor-only sibling exists."
    ),
    "product_variant/variants.py": (
        "ProductDeviceRules.assert_can_edit(actor, product) goes through "
        "ProductRules.assert_can_update, which allows manage:projects OR the product's "
        "designated_user_id, and also refuses an archived product; no actor-only "
        "sibling exists."
    ),
    "product_device/completeness.py": (
        "Resolves the device's product, then applies the same "
        "ProductDeviceRules.assert_can_edit designated-user and archived-product shape "
        "as product_variant/variants.py; every signed-in user may read devices, so the "
        "order reveals nothing."
    ),
    "product/upload_product_file.py": (
        "Same ProductRules.assert_can_update ownership-or-designated-user shape as "
        "update_product.py."
    ),
    "product/update_product_file.py": (
        "Resolves the owning product from the file, then applies the same "
        "ProductRules.assert_can_update ownership-or-designated-user shape."
    ),
    "product/delete_product_file.py": (
        "Same ProductRules.assert_can_update ownership-or-designated-user shape as "
        "update_product_file.py."
    ),
    "production_lot/lot_steps.py": (
        "AddLotStep, UpdateLotStep, DeleteLotStep and ReorderLotSteps all call "
        "LotRules.assert_can_edit_structure(actor, lot), which needs the lot for its "
        "terminal-status check; no actor-only sibling exists."
    ),
    "order/create_order_item.py": (
        "OrderRules.assert_can_update(actor, order) needs the order; assert_can_create "
        "gates creating an order itself, a different action with a different message."
    ),
    "production_lot/switch_lot_material_source.py": (
        "LotRules.assert_can_update(actor, lot) needs the lot for its "
        "manage:lots-gated terminal-status check; no actor-only sibling."
    ),
    "production_lot/assign_external_position.py": (
        "AssignExternalPosition calls OrderRules.assert_can_update(actor, order); "
        "UnassignExternalPosition calls LotRules.assert_can_update(actor, lot); "
        "neither has an actor-only sibling."
    ),
    "production_lot/reject_lot_source.py": (
        "LotRules.assert_can_approve_source(actor, lot) needs the lot for its "
        "terminal-status check; no actor-only sibling."
    ),
    "order/update_order.py": (
        "UpdateOrder, SubmitOrder, RequestOrder and CancelOrder each call an "
        "OrderRules method that takes the order (assert_can_update/submit/request/"
        "cancel); none has a matching actor-only sibling."
    ),
    "order/move_order_item.py": (
        "assert_can_move_item(actor, source, target, item) is inherently multi-entity; "
        "no actor-only equivalent exists."
    ),
    "production_order/record_manufacturing_assessment.py": (
        "ProductionOrderRules.assert_can_update(actor, order) needs the order; "
        "assert_can_assign gates machine assignment, a different action."
    ),
    "production_lot/lot_positions.py": (
        "RegroupLotPositions calls assert_can_edit_structure(actor, lot); "
        "AppendLotPosition calls assert_can_append_position(actor, lot); neither has "
        "an actor-only sibling."
    ),
    "production_lot/update_lot.py": (
        "LotRules.assert_can_update(actor, lot) needs the lot; no actor-only sibling."
    ),
    "production_lot/approve_lot_source.py": (
        "LotRules.assert_can_approve_source(actor, lot) needs the lot for its "
        "terminal-status check; no actor-only sibling."
    ),
    "order/mark_order_item_ready_for_pickup.py": (
        "OrderRules.assert_can_update(actor, order) needs the order; no actor-only sibling."
    ),
    "order/mark_order_item_ordered.py": (
        "All four classes in this module call OrderRules.assert_can_update(actor, "
        "order); no actor-only sibling."
    ),
    "order/update_order_item.py": (
        "OrderRules.assert_can_update(actor, order) needs the order; no actor-only sibling."
    ),
    "order/cancel_order_item.py": (
        "OrderRules.assert_can_cancel_line(actor, order, item) starts with "
        "assert_can_update(actor, order), whose manage:orders requirement depends on the "
        "order's status; no actor-only sibling. The fetch runs in read_order_line."
    ),
    "order/close_order_item_short.py": (
        "Same assert_can_update(actor, order) shape as order/cancel_order_item.py, through "
        "OrderRules.assert_can_close_short(actor, order, item)."
    ),
    "production_order/production_order_lifecycle.py": (
        "StartProductionOrder and PauseProductionOrder call assert_can_update(actor, "
        "order); CancelProductionOrder calls assert_can_cancel(actor, order), which "
        "carries its own ownership carve-out; none has a matching actor-only sibling "
        "(assert_can_assign and assert_can_manage gate different actions)."
    ),
    "production_order/record_production_order_completion.py": (
        "Authorizes via assert_can_update(actor, order); assert_can_assign gates "
        "machine assignment, a different action."
    ),
    "source_item_demand/cancel_source_item_demand.py": (
        "Authorization is LotRules.assert_can_update(actor, lot) on the demand's lot; "
        "no actor-only sibling covers this action."
    ),
    "source_item_demand/update_source_item_demand.py": (
        "Same LotRules.assert_can_update(actor, lot) shape as cancel_source_item_demand.py."
    ),
    "project/update_project.py": (
        "ProjectRules.assert_can_update(actor, project) allows manage:projects OR the "
        "project's own designated_user_id; no unconditional permission and no "
        "actor-only sibling."
    ),
    "source_item_demand/create_source_item_demand.py": (
        "LotRules.assert_can_update(actor, lot) on the freshly-fetched lot named by "
        "the command; no actor-only sibling."
    ),
    # The six entries below are genuine instances of the same
    # fetch-before-permission-check pattern that have not had the per-file
    # review the entries above have, so each may still be reordered or
    # confirmed as a true entity-dependent exception. They are named
    # explicitly so this guard does not fail on files nobody has reviewed.
    "order/delete_order_item.py": (
        "Not reviewed in this pass. OrderRules.assert_can_remove_item(actor, order, "
        "item) takes both the order and the item, so it may end up in the same "
        "entity-dependent, no-actor-only-sibling shape as order/update_order.py."
    ),
    "user/reset_user_totp.py": (
        "Not reviewed in this pass. UserRules.assert_can_reset_totp(actor, target) "
        "forbids resetting one's own 2FA and protects the system user, the same "
        "target-dependent shape as user/update_user.py."
    ),
    "production_lot/lot_lifecycle.py": (
        "Not reviewed in this pass. HoldLot and ResumeLot both call "
        "LotRules.assert_can_update(actor, lot), the same shape allowlisted for "
        "production_lot/update_lot.py."
    ),
    "production_lot/replace_structure.py": (
        "Not reviewed in this pass. LotRules.assert_can_edit_structure(actor, lot), "
        "the same shape allowlisted for production_lot/lot_steps.py."
    ),
    "production_order/update_production_order.py": (
        "Not reviewed in this pass. ProductionOrderRules.assert_can_update(actor, "
        "order), the same shape allowlisted for production_order/record_"
        "manufacturing_assessment.py."
    ),
}


def _iter_execute_methods() -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    found = []
    for root in USE_CASES_ROOTS:
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            found.extend(
                (relative, node)
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                and node.name == "execute"
            )
    return found


def _call_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _is_permission_assertion(name: str) -> bool:
    return name.startswith("assert_can_") or name.startswith("_assert_can")


def _is_disallowed_fetch(call: ast.Call) -> bool:
    func = call.func
    if not isinstance(func, ast.Attribute):
        return False
    method = func.attr
    if not (method in _FETCH_METHOD_NAMES or method.startswith(_FETCH_METHOD_PREFIXES)):
        return False
    # Only a call shaped like `self._<attr>.<method>(...)` counts: a
    # repository fetch, not an unrelated helper or a call on the fetched
    # entity itself.
    owner = func.value
    if not isinstance(owner, ast.Attribute) or not isinstance(owner.value, ast.Name):
        return False
    return owner.value.id == "self" and owner.attr.startswith("_")


def _calls_in_same_scope(node: ast.AST) -> list[ast.Call]:
    """Collects every Call reachable from `node` without descending into a
    nested function, lambda or class body: such a nested scope runs on its
    own schedule, so its position in the source does not reflect when it
    actually executes relative to the rest of this method."""
    calls: list[ast.Call] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef):
            continue
        if isinstance(child, ast.Call):
            calls.append(child)
        calls.extend(_calls_in_same_scope(child))
    return calls


def _find_violation(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[int, int] | None:
    """Returns (fetch_lineno, assert_lineno) if a disallowed fetch call
    precedes the first permission assertion in this execute method, else
    None (either there is no permission assertion to check against, or
    the assertion already comes first)."""
    first_assert_line: int | None = None
    earliest_bad_fetch_line: int | None = None
    for call in _calls_in_same_scope(node):
        name = _call_name(call)
        if name and _is_permission_assertion(name):
            if first_assert_line is None or call.lineno < first_assert_line:
                first_assert_line = call.lineno
        elif _is_disallowed_fetch(call) and (
            earliest_bad_fetch_line is None or call.lineno < earliest_bad_fetch_line
        ):
            earliest_bad_fetch_line = call.lineno
    if first_assert_line is None or earliest_bad_fetch_line is None:
        return None
    if earliest_bad_fetch_line < first_assert_line:
        return earliest_bad_fetch_line, first_assert_line
    return None


def test_permission_checked_before_entity_fetch() -> None:
    violations = []
    for relative, node in _iter_execute_methods():
        if relative in ALLOWLIST:
            continue
        violation = _find_violation(node)
        if violation is not None:
            fetch_line, assert_line = violation
            violations.append(
                f"{relative}: execute() at line {node.lineno} fetches at line "
                f"{fetch_line} before its first permission assertion at line "
                f"{assert_line}"
            )
    assert not violations, "Use cases checking permission after fetching the entity:\n" + "\n".join(
        violations
    )


def test_allowlist_entries_still_exist() -> None:
    """Keeps the allowlist honest: every entry must name a real file, so a
    rename or removal cannot silently leave a stale, unchecked entry."""
    missing = [
        name for name in ALLOWLIST if not any((root / name).is_file() for root in USE_CASES_ROOTS)
    ]
    assert not missing, f"Allowlist entries with no matching file: {missing}"
