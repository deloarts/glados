"""
The queue-scope locks (IProductionOrderRepository.lock_queue_scope) of a use
case that draws queue places. They come before any row lock, because
Auto-Plan, a reorder and a reassignment hold a scope while they write the
order rows of that queue; a writer that held a row and then waited for the
scope could close a cycle with them. The scope is known before the locks
from the command or from an unlocked read of the order. When the locked
read shows that the order moved to another queue in between, the scope held
is the wrong one and taking the right one now would invert the order, so
the request answers ConcurrentModificationError and is repeated on the
current state. Several scopes are locked in one sorted order: machines, then
pools, then the unassigned queue, ascending ids within each.

Two writers learn their queue only after their row locks and keep taking it
then: a disposition that queues the inspection of a follow-up lot, and the
lifecycle reconciler giving a revived order a free place. Postgres resolves
a rare cycle with them by aborting one transaction with a deadlock error,
which the server retries once (LostRaceRetryMiddleware) before it answers a
retryable 503.
"""

from collections.abc import Iterable

from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.domain.exceptions import ConcurrentModificationError

QueueScope = tuple[int | None, int | None]


def queue_scope_key(machine_id: int | None, machine_pool_id: int | None) -> QueueScope:
    """The queue a (machine, pool) pair draws its place from: the machine's
    when one is set, else the pool's own, else the unassigned queue, as
    next_queue_sequence resolves it."""
    if machine_id is not None:
        return (machine_id, None)
    return (None, machine_pool_id)


def _sort_key(scope: QueueScope) -> tuple[bool, int, bool, int]:
    machine_id, pool_id = scope
    return (machine_id is None, machine_id or 0, pool_id is None, pool_id or 0)


async def lock_queue_scopes_first(
    order_repo: IProductionOrderRepository, scopes: Iterable[QueueScope]
) -> frozenset[QueueScope]:
    """Locks the queues of `scopes` in the one sorted order, before the
    caller takes any row lock, and returns their keys for
    assert_queue_scope_held."""
    by_key: dict[QueueScope, QueueScope] = {}
    for machine_id, pool_id in scopes:
        by_key.setdefault(queue_scope_key(machine_id, pool_id), (machine_id, pool_id))
    for key in sorted(by_key, key=_sort_key):
        await order_repo.lock_queue_scope(*by_key[key])
    return frozenset(by_key)


def assert_queue_scope_held(
    held: frozenset[QueueScope],
    machine_id: int | None,
    machine_pool_id: int | None,
    production_order_id: int,
) -> None:
    """Refuses a queue place in a queue whose lock was not taken before the
    row locks, because the order moved there after the caller read it."""
    if queue_scope_key(machine_id, machine_pool_id) not in held:
        raise ConcurrentModificationError(
            f"Production order #{production_order_id} was moved to another queue while "
            "this request was waiting for it. Reload and try again."
        )
