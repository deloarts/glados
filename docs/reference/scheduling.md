# scheduling

The exact behaviour of the schedule walk and of Auto-Plan: how an order's window is placed, which windows are kept, when the walk runs, how Auto-Plan reads, places and writes, the tenant timezone, machine calendars and machine capability. The concept is in [CONTRIBUTING.md section 11](../CONTRIBUTING.md#11-scheduling-and-auto-plan).

- [1 the forward walk](#1-the-forward-walk)
  - [1.1 where an order starts](#11-where-an-order-starts)
  - [1.2 running orders and kept windows](#12-running-orders-and-kept-windows)
  - [1.3 machines without working time](#13-machines-without-working-time)
- [2 passes and chain cycles](#2-passes-and-chain-cycles)
- [3 when the walk runs](#3-when-the-walk-runs)
- [4 Auto-Plan](#4-auto-plan)
  - [4.1 read, place and write](#41-read-place-and-write)
  - [4.2 candidates and anchors](#42-candidates-and-anchors)
  - [4.3 planning levels](#43-planning-levels)
- [5 the tenant timezone](#5-the-tenant-timezone)
- [6 machine calendars and downtime](#6-machine-calendars-and-downtime)
- [7 machine capability](#7-machine-capability)

## 1 the forward walk

The walk lives in `src/modules/fulfillment/domain/services/scheduling/` and places each machine's queue in `queue_sequence` order.

### 1.1 where an order starts

- An order starts at the later of the previous order's planned end and its earliest start.
- The earliest start is the latest of `not_before`, the readiness of every earlier open position of its lot, and, for sequence 1, the raw material's expected delivery.
- A queued order also never starts before the internal work of its earlier positions ends, taken as a moment (`predecessor_ready_moment`), so a successor on another machine does not start on its predecessor's last day while that predecessor still runs.
- An order stays undated when an earlier open position has no date at all, or when its raw material has neither arrived nor a forecast, unless parts are already waiting at its step.
- A queued order never starts before now, so a readiness date in the past does not plan it in the past.
- The walk writes no window onto an order that was completed or canceled, re-pinned or moved to another queue place after the walk read it.

### 1.2 running orders and kept windows

- Running orders come first on their machine, wherever they sit in the queue, since the machine is busy with them now.
- A running order anchors at its latest start or resume, which may lie in the past: the end of its latest closed interruption, or else `actual_start`, because `actual_start` keeps the first start for the net work time.
- Pinned orders keep their window.
- A queued order whose planned start lies within the production setting `frozen_window_hours` from now keeps its window too. Its context is `frozen` and its earliest start is explained as `frozen`, so a recompute does not shift the shop floor's next hours.
- Auto-Plan and manual edits still move a frozen order, since a placement, a reassign or a reorder drops the moved order's window for the walk to place it again.
- A kept window or a running anchor never moves the next order's start back.
- A kept window or running anchor that begins before the previous order on its queue ends, a second running order on one machine included, is flagged `window_overlap`.
- A kept window that begins before the previous step of its lot is ready (the same moment a queued order would wait for) is flagged `window_before_predecessor` and kept too.

### 1.3 machines without working time

- A machine whose calendar holds no working time, such as a week of zero hours or a downtime that never ends, leaves only its own queue undated, flagged `no_working_time`.
- A pool places its orders on a member that works.
- Every walk, Auto-Plan's included, cuts open and upcoming downtimes out of the machine calendars.
- An open downtime blocks the rest of the local day from its start, so one reported ahead blocks its own day and marks the machine down only once it begins.

## 2 passes and chain cycles

- One pass of the walk reads the readiness of earlier positions from before the walk, so the walk repeats until no readiness changes (`schedule_all_propagated`).
- An acyclic set of lot chains settles within one pass per position plus one, which is the pass limit.
- An order still moving at the limit is named in `unsettled_order_ids` and logged with a warning. This is a safety net only.
- Before the passes the walk looks for wait cycles (`chain_cycles.py`), such as a step queued ahead of its own predecessor on one machine, and leaves the orders on one undated, flagged `chain_cycle`, so they take no capacity and no date runs away.
- The later steps of their lots wait for the cycle's orders as for any undated predecessor.
- A cycle through a pool, whose orders go to whichever member finishes first, is not in that graph. The orders it keeps moving to the pass limit are walked once more undated and flagged the same way, so no runaway date is kept.
- Auto-Plan keeps the orders of one lot in position order in every ordering, so it never creates such a cycle itself.

## 3 when the walk runs

- A write that can move a planned date requests a walk of the whole schedule after its commit (`recompute_schedule_after_commit`).
- Besides the order, lot and line writers, these writes are the machine calendars, working hours, exceptions and downtimes, tenant holidays, the production and general settings, machine pools, a machine's update, archive and restore, a lot step's delete and reorder, a position regroup, a supplier or fabrication method change (their lead times date external steps) and a line moved to another supplier.
- In the app the request only draws a coalescing generation and stages a `ScheduleRecomputeRequested` event (`RecomputeMachineSchedule` built with `defer`).
- The `schedule` event worker walks on a fresh session, skipping a walk that a concurrent one already covered.
- A tick in every worker walks every 15 minutes and right after tenant midnight too (`schedule_tick.py`).
- Every walk holds the `SCHEDULE_RECOMPUTE` advisory lock, also while Redis, which only coalesces, is down.
- The board's "schedule stale since" mark is set before a request draws its generation, so the walk that covers it clears it, and a walk that fails puts it back.
- A worker that skips a covered generation clears the mark too when no newer generation is drawn, since a mark set while the covering walk ran is otherwise left for the next tick.
- Auto-Plan walks in the request, since its answer is the plan. A walk that fails after Auto-Plan committed its plan is logged while the answer stays the plan.
- The tests walk in the request too (`SCHEDULING__RECOMPUTE_IN_BACKGROUND`).

## 4 Auto-Plan

Auto-Plan lives in `src/modules/fulfillment/application/use_cases/production_schedule/auto_plan.py`.

### 4.1 read, place and write

- Auto-Plan runs in three parts, like the walk.
- It reads its machines, the queues and the scheduling data in a transaction that commits before the placement.
- The placement runs on copies of the orders without any lock held.
- The write locks every queue it may write, the unassigned one included, and the queued orders in them, and reads the queues again.
- A queue that no longer holds the orders it held at the read keeps its state, because an order in it was started, pinned, moved, added, canceled or completed meanwhile. A placement out of it or into it is not written and is reported as skipped with the reason `changed_while_planning`, and a run on the current queues places it again.
- A machine archived meanwhile stops the run with 409 `ConcurrentModificationError`.
- A write that lost a race (a deadlock, a serialization failure or a lock wait that hit `lock_timeout`) is rolled back and written once more against the queues as they are then. The read committed, so `LostRaceRetryMiddleware` cannot repeat the request itself.
- A start takes its machine's queue lock before its row locks, like every queue writer, so it waits only for Auto-Plan's short write.

### 4.2 candidates and anchors

- Auto-Plan only moves `QUEUED` orders.
- Pinned, running, paused and out-of-scope orders, and by default orders planned for today, are anchors that candidates are placed around.
- A run on some machines leaves an order without a machine alone when only machines outside the run could take it, such as another team's work. At the `pools` level that is when none of its eligible pools has a member in the run, and at the `machines` level when no machine in the run is eligible.
- An order nothing at all could take stays a candidate, so its skip is reported.
- A manual or unassigned inspection step without a machine is no candidate either, since the walk dates it, unless it waits on material.
- The live progress stream reports exactly the candidates the result reports, and every skip carries its reason.
- A candidate Auto-Plan cannot place keeps its queue place unless a placement of the run went into that queue, so a run that places nothing, or a candidate of an archived pool, changes no queue.
- Machines that are down right now are never trial-placed, and Auto-Plan excludes them from its run.
- `overwrite_pinned` makes pinned orders movable and clears the pin of any order it moves.

### 4.3 planning levels

- Without `assign_machines` a candidate is only re-sequenced on the machine it already has.
- Pool-assigned orders are always resolved to a capable pool member at the `machines` planning level.
- At the `pools` level Auto-Plan never writes `machine_id` and treats machine-resolved orders as anchors.
- Manual and inspection positions are never pool-assigned, and Auto-Plan never invents a machine for an inspection step.

## 5 the tenant timezone

- Today is the current date in the tenant's default timezone, the general admin setting `default_timezone`.
- An order counts as planned for today when its planned window, converted from the stored UTC to that timezone, touches that date, so an order planned from 23:30 to 00:30 local time belongs to both local days.
- A machine calendar's hours are local to that timezone. Each day holds intervals of a local start time and a length of at most 1440 minutes.
- An interval belongs to the day it starts on also when it runs past midnight, and it is converted to UTC with its own day's offset, so the hours keep their local time across a daylight saving change.
- Touching windows of consecutive days merge, and a downtime is cut out of the windows where it falls.
- Every other day in the scheduling package is a day of that timezone too, while stored instants stay UTC.
- An instant counts on the local day it falls on. This covers a planned end against the lot's target date (an order ending at 23:30 UTC on its target date is late in Vienna, where it is already the next day), an actual delivery, a ready-for-pickup event or a planned end as a readiness date, and a running order's start in the earliest-start explanation.
- A day used as a floor, such as `not_before` or a readiness date, starts at local midnight with that day's own offset, also on a daylight saving switch.
- The waiting flag, the critical ratio ordering, the planning exceptions' late check and the QA worklist's future filter compare with the local today.
- The zone is passed explicitly. Each `OrderSchedulingContext` carries it as `zone`, the readiness resolvers take it as a parameter, the walk callers pass it to `build_contexts`, and the read paths resolve it from `SchedulingRepos.settings`.

## 6 machine calendars and downtime

- A machine's working time per weekday comes from its own `MachineWorkingHours.weekly_hours` or, without one, from `AdminProductionSettings.default_weekly_hours`.
- Per weekday that is a list of intervals, each a local start time and a length in minutes (`value_objects/work_interval.py`).
- A `MachineCalendarException` replaces one date on top of either with one interval from its `start_minute`, such as a maintenance window, an extra shift or a machine open on a holiday.
- A `TenantHoliday` (Resources, Holidays) closes every machine from its start to its end date, under the machine's exceptions.
- A `MachineDowntime` is a window in which the machine is down, open until it comes back up. The walk cuts downtimes out of the calendar's working windows (section 1.3).

## 7 machine capability

- Machine capability lives in `production_order_rules.py` and is mirrored by the frontend's `useMachineCapability`.
- A machine covers a position when its fabrication methods include every method of the position's steps that requires a machine.
- A position whose steps are all manual is queued without a machine or pool.
- An inspection step always forms a position of its own, goes only to a QA machine (`is_qa_machine`) and never to a pool.
- A QA machine never takes fabrication work.
- A pool covers the intersection of its members' methods.
