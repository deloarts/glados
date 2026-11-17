---
title: Planning
summary: How to read the Gantt chart on the Planning tab, where its dates come from and where you change the plan it shows.
sourceRefs:
  - frontend/src/features/production/planning/views/ProductionPlanningView.vue
  - frontend/src/features/production/utils/productionPlanningTasks.ts
  - backend/src/modules/fulfillment/application/use_cases/production_schedule/recompute_machine_schedule.py
lastVerified: 2026-11-10
---

The **Planning** tab under Production draws every queued, running and paused production order as a bar on a timeline, grouped by machine. It answers when each order is expected to run and what it waits for. The chart only reads the plan, so you cannot drag bars here. It updates by itself when an order, a lot or a machine changes.

## Reading the chart {#rows}

Each machine is a group, named with the fabrication methods it covers, and its orders follow in queue order. **No Assignment** collects the orders without a machine, which includes orders on a pool that no machine has taken yet. **External Steps** shows the supplier steps of the same lots, labelled with the order number and the supplier. A supplier step without an expected delivery date is marked as date pending and sits at its earliest possible point.

A bar is labelled with the lot number, the part number, the position and its fabrication method. Its fill shows how much of the quantity is completed. The arrows connect each step of a lot to the step before it, supplier steps included, so you can follow why a bar starts where it does. The vertical line marks the current time.

The table on the left lists **Machine / Order Number**, **Status**, **Start** and **Duration (days)**, and you can sort by each column. **Days**, **Weeks** and **Months** change the scale of the timeline.

## Conflicts {#conflicts}

A bar with an orange outline has a scheduling conflict, for example **Past target date**, **Machine down** or **Waiting on material**. The same conflicts show as tags on the order's card on the [Queue Board](/handbook/production/queue), with a tooltip that explains each one.

## Where the dates come from {#dates}

The dates are the production schedule itself, worked out from each machine's queue, its working hours, the lot's steps and the material. A new order that the schedule has not dated yet gets a rough estimate until it has. The [Capacity](/handbook/production/capacity) tab shows the same schedule as booked and free hours per day.

## Changing the plan {#changes}

To change the plan, reorder or move orders on the [Queue Board](/handbook/production/queue), assign steps through [Manage Production](/handbook/production/manage-production), or let [Auto-Plan](/handbook/production/auto-plan) rearrange the queues. The chart follows within moments.

## Examples {#examples}

A lot has a turning step and a milling step. The milling bar starts where the turning bar ends, and an arrow links the two.

An order sits under **No Assignment**. It is on a pool, and it moves to a machine group once the operator starts it on one of the pool's machines.

A bar has an orange outline because its lot will miss the target date. Moving the order up its machine's queue on the Queue Board pulls the bar earlier, and the outline goes once the order ends in time.
