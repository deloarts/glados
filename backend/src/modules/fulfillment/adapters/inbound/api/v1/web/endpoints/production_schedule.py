"""Deep scheduling: read-only schedule board + capacity, the manual
auto-planner trigger, and its live-progress SSE sibling.
"""

import asyncio
import dataclasses
import json

import redis
from fastapi import Depends
from fastapi.routing import APIRouter
from sse_starlette.sse import EventSourceResponse

from src.modules.fulfillment.adapters.inbound.api.deps.production import build_auto_plan_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_auto_plan_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_schedule_board_use_case
from src.modules.fulfillment.adapters.inbound.api.schemas.production_schedule_schema import (
    AutoPlanRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_schedule_schema import (
    AutoPlanResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_schedule_schema import (
    AutoPlanRunResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_schedule_schema import (
    AutoPlanRunStatusResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_schedule_schema import (
    ScheduleBoardFilterParams,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_schedule_schema import (
    ScheduleBoardResponse,
)
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanCommand
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanProgress
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanResult
from src.modules.fulfillment.application.dto.production_schedule_dto import ScheduleBoardResult
from src.modules.fulfillment.application.use_cases.production_schedule.auto_plan import AutoPlan
from src.modules.fulfillment.application.use_cases.production_schedule.get_schedule_board import (
    GetScheduleBoard,
)
from src.modules.fulfillment.domain.errors import AutoPlanRunInProgressError
from src.modules.fulfillment.domain.services.production_order_rules import ProductionOrderRules
from src.modules.fulfillment.infrastructure.autoplan_run_registry import heartbeat_once
from src.modules.fulfillment.infrastructure.autoplan_run_registry import read as read_autoplan_run
from src.modules.fulfillment.infrastructure.autoplan_run_registry import (
    release as release_autoplan_run,
)
from src.modules.fulfillment.infrastructure.autoplan_run_registry import try_acquire
from src.modules.fulfillment.infrastructure.autoplan_run_registry import update_snapshot
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.streamed_run import StreamedRun
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.events.registry import LIVE_CHANNEL
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.redis_client import get_async_redis_client
from src.modules.platform.ports.outbound.live_signal import LiveResource
from src.modules.platform.ports.outbound.live_signal import LiveSignal

router = APIRouter()


async def _publish_run_signal(actor_id: int) -> None:
    """Publishes the `auto-plan-run` refetch hint on run start and end. Best
    effort, since clients also recover through the status endpoint."""
    signal = LiveSignal(
        resource=LiveResource.AUTO_PLAN_RUN, id=0, action="updated", actor_id=actor_id
    )
    try:
        await get_async_redis_client().publish(
            LIVE_CHANNEL, json.dumps([dataclasses.asdict(signal)])
        )
    except redis.RedisError:
        log.warning("Auto-plan run signal: failed to publish; dropping.")


@router.get("/", response_model=ScheduleBoardResponse)
async def read_schedule_board(
    params: ScheduleBoardFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: GetScheduleBoard = Depends(get_schedule_board_use_case),
) -> ScheduleBoardResult:
    return await use_case.execute(date_from=params.date_from, date_to=params.date_to)


@router.post("/auto-plan", response_model=AutoPlanResponse)
async def auto_plan(
    body: AutoPlanRequest,
    actor: User = Depends(get_current_active_user),
    use_case: AutoPlan = Depends(get_auto_plan_use_case),
) -> AutoPlanResult:
    """Proposes (and applies) a priority/EDD-driven placement for every
    eligible unpinned QUEUED order; pinned/IN_PROGRESS orders are never
    touched. Returns a before/after diff."""
    cmd = AutoPlanCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


# Strong references to every in-flight stream run. The event loop only
# holds weak references to tasks, so without this set a run whose client
# has disconnected could be garbage-collected mid-flight.
_RUN_TASKS: set[asyncio.Task[None]] = set()


@router.post("/auto-plan/stream")
async def auto_plan_stream(
    body: AutoPlanRequest,
    actor: User = Depends(get_current_active_user),
) -> EventSourceResponse:
    """Run auto-plan like `POST /auto-plan`, with the same inputs and
    outcome, but stream stage and per-candidate progress over SSE. The
    stream ends with exactly one `result` frame (the `/auto-plan` response
    body) or one `error` frame. Only one run may be in progress app-wide;
    another caller gets 409 before any stream opens. A client that
    disconnects does not stop the run, which still commits or rolls back as
    a whole."""
    # The task model, the mutex heartbeat and the shutdown behaviour live in
    # StreamedRun (streamed_run.py).
    # The permission check happens BEFORE the response starts, so a
    # forbidden caller gets a plain 403; no stream is ever opened for them.
    ProductionOrderRules.assert_can_assign(actor)
    cmd = AutoPlanCommand(**body.model_dump())

    run: StreamedRun[AutoPlanProgress] = StreamedRun(
        label="Auto-plan",
        execute=lambda db, progress: build_auto_plan_use_case(db).execute(
            actor=actor, cmd=cmd, progress=progress
        ),
        # The same shape as the plain /auto-plan response.
        response_model=AutoPlanResponse,
        snapshot=lambda handle, event: update_snapshot(
            handle, event.stage, event.current, event.total
        ),
        heartbeat_once=heartbeat_once,
        release=release_autoplan_run,
        on_end=lambda: _publish_run_signal(actor.id),
    )

    # Acquired as late as possible; a loser gets a 409 before any stream.
    handle = await try_acquire(actor.id, actor.full_name or actor.username)
    if handle is None:
        raise AutoPlanRunInProgressError(
            "Another auto-plan run is already in progress. Try again once it finishes."
        )

    # Not awaited, so a client disconnect never aborts the run.
    response = await run.start(handle, _RUN_TASKS)

    # Only once the run is actually underway.
    await _publish_run_signal(actor.id)
    return response


@router.get("/auto-plan/status", response_model=AutoPlanRunStatusResponse)
async def auto_plan_status(
    _: User = Depends(get_current_active_user),
) -> AutoPlanRunStatusResponse:
    """The source of truth for every client that is not itself the runner:
    late joiners, page reloads, reconnects and the observer dialog's poll
    all recover through this rather than depending on having received the
    `auto-plan-run` live signal. Any authenticated user may call it;
    unlike the stream/plain endpoints, there is no write permission gate
    here, only visibility."""
    state = await read_autoplan_run()
    run = (
        AutoPlanRunResponse.model_validate(state, from_attributes=True)
        if state is not None
        else None
    )
    return AutoPlanRunStatusResponse(running=run is not None, run=run)
