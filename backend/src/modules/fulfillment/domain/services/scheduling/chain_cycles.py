"""Finds the orders a lot chain cycle keeps from ever settling.

An order waits for the order ahead of it on its machine (through the
machine's cursor) and for every order of the earlier open positions of its
lot. When a step is queued ahead of its own predecessor on one machine,
these waits form a cycle: each pass of the walk pushes the step behind its
predecessor and the predecessor behind the step, so the dates run away
until the pass limit stops them. The walk instead leaves the orders of such
a cycle undated. They take no capacity then, so the orders behind them on
their machine are placed as usual, and a later step of their lot stays
undated by the walk's own rule for a predecessor without a date.

Only waits that move a date count. A running order keeps its anchor and a
pinned or frozen order its window, so nothing they wait on moves them, and
a paused order takes no capacity, so the next order does not wait on it.
Pool queues are left out, since a pool places each order on whichever
member finishes it first rather than behind a fixed predecessor.
"""

from collections.abc import Iterable
from collections.abc import Iterator

from src.modules.fulfillment.domain.services.scheduling.walk_context import OrderSchedulingContext
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus

type _Node = tuple[str, int, int]


def cycle_blocked_order_ids(
    machine_queues: dict[int, list[OrderSchedulingContext]],
    manual_queue: list[OrderSchedulingContext],
    every_context: Iterable[OrderSchedulingContext],
) -> frozenset[int]:
    """The ids of the orders on a wait cycle. `every_context` is every
    order the walk places, so a predecessor in a pool or without a machine
    counts."""
    contexts = list(every_context)
    edges: dict[_Node, set[_Node]] = {}
    for key, queue in sorted(machine_queues.items()):
        _add_queue_waits(edges, key, queue)
    _add_queue_waits(edges, -1, manual_queue)
    _add_predecessor_waits(edges, contexts)
    return frozenset(
        node[1]
        for component in _strong_components(edges)
        if len(component) > 1
        for node in component
        if node[0] == "order"
    )


def _order(order_id: int) -> _Node:
    return ("order", order_id, 0)


def _moves(ctx: OrderSchedulingContext) -> bool:
    """Whether the walk places the order from what it waits on."""
    if ctx.status != ProductionOrderStatus.QUEUED:
        return False
    keeps_window = ctx.existing_planned_start is not None and ctx.existing_planned_end is not None
    return not ((ctx.pinned or ctx.frozen) and keeps_window)


def _walk_order(ctx: OrderSchedulingContext) -> tuple[bool, int, int]:
    running = ctx.status == ProductionOrderStatus.IN_PROGRESS and ctx.actual_start is not None
    return (not running, ctx.queue_sequence, ctx.order_id)


def _add_queue_waits(
    edges: dict[_Node, set[_Node]], key: int, queue: list[OrderSchedulingContext]
) -> None:
    """The machine's cursor after each order waits on that order and on
    the cursor before it; an order the walk places waits on the cursor
    before it."""
    previous: _Node | None = None
    walked = sorted(
        (ctx for ctx in queue if ctx.status != ProductionOrderStatus.PAUSED),
        key=_walk_order,
    )
    for index, ctx in enumerate(walked):
        order = _order(ctx.order_id)
        cursor: _Node = ("cursor", key, index)
        edges.setdefault(order, set()).add(cursor)
        if previous is not None:
            edges.setdefault(previous, set()).add(cursor)
            if _moves(ctx):
                edges.setdefault(previous, set()).add(order)
        previous = cursor


def _add_predecessor_waits(
    edges: dict[_Node, set[_Node]], contexts: list[OrderSchedulingContext]
) -> None:
    """An order the walk places waits on every order of the earlier open
    positions of its lot."""
    orders_by_position: dict[int, list[int]] = {}
    for ctx in contexts:
        if ctx.lot_position_id is not None:
            orders_by_position.setdefault(ctx.lot_position_id, []).append(ctx.order_id)
    for ctx in contexts:
        if not _moves(ctx):
            continue
        for predecessor in ctx.predecessor_positions:
            for order_id in orders_by_position.get(predecessor.position_id, []):
                edges.setdefault(_order(order_id), set()).add(_order(ctx.order_id))


def _strong_components(edges: dict[_Node, set[_Node]]) -> Iterator[list[_Node]]:
    return _Tarjan(edges).components()


class _Tarjan:
    """Tarjan's strongly connected components, iteratively, so a long
    queue cannot exhaust the recursion limit."""

    def __init__(self, edges: dict[_Node, set[_Node]]) -> None:
        self._edges = edges
        self._index: dict[_Node, int] = {}
        self._low: dict[_Node, int] = {}
        self._on_stack: set[_Node] = set()
        self._stack: list[_Node] = []
        self._work: list[tuple[_Node, Iterator[_Node]]] = []

    def components(self) -> Iterator[list[_Node]]:
        nodes = sorted(set(self._edges) | {n for targets in self._edges.values() for n in targets})
        for root in nodes:
            if root in self._index:
                continue
            self._enter(root)
            while self._work:
                node, successors = self._work[-1]
                if self._descend(node, successors):
                    continue
                self._work.pop()
                if self._work:
                    parent = self._work[-1][0]
                    self._low[parent] = min(self._low[parent], self._low[node])
                if self._low[node] == self._index[node]:
                    yield self._pop_component(node)

    def _enter(self, node: _Node) -> None:
        self._index[node] = self._low[node] = len(self._index)
        self._stack.append(node)
        self._on_stack.add(node)
        self._work.append((node, iter(sorted(self._edges.get(node, ())))))

    def _descend(self, node: _Node, successors: Iterator[_Node]) -> bool:
        """Enters the next unvisited successor and reports whether it did,
        lowering the node's link through the successors on the stack."""
        for successor in successors:
            if successor not in self._index:
                self._enter(successor)
                return True
            if successor in self._on_stack:
                self._low[node] = min(self._low[node], self._index[successor])
        return False

    def _pop_component(self, node: _Node) -> list[_Node]:
        component: list[_Node] = []
        while True:
            member = self._stack.pop()
            self._on_stack.discard(member)
            component.append(member)
            if member == node:
                return component
