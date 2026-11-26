---
title: How Auto-Plan works
summary: How to run Auto-Plan, how to read its result, what the planning level changes and how the six algorithms differ.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_schedule/auto_plan.py
  - backend/src/modules/fulfillment/domain/value_objects/auto_plan_algorithm.py
  - frontend/src/features/production/components/AutoPlanDialog.vue
  - backend/src/modules/fulfillment/application/use_cases/production_schedule/_redated.py
lastVerified: 2026-11-26
---

<script setup lang="ts">
import AutoPlanAlgorithmCards from '@/features/production/planning/components/AutoPlanAlgorithmCards.vue'
</script>

Auto-Plan rebuilds the machine queues in one run. It sorts the queued orders it may move by the algorithm you pick and places each one on a machine or pool, around the orders it must leave alone. The rules it follows are on [How Auto-Plan places orders](/handbook/production/auto-plan-rules) and [When an order can start](/handbook/production/auto-plan-timing).

<Message severity="warn" :closable="false">
Auto-Plan writes its result straight away. There is no preview and no confirm step, and the table you see afterwards shows what it already changed.
</Message>

## Running it {#run}

You open Auto-Plan with the **Auto-Plan** button on the Lots tab or the Capacity tab. The button needs **Write Production Orders** and shows disabled with a tooltip without it. In the dialog you pick the **Planning algorithm** and the **Planning level**, and you untick any machine under **Machines to include** that the run should leave alone. **Allow assigning machines** is off by default, so an order only moves within the machine it already has. **Allow overwriting user-planned dates** is off by default, so pinned orders stay where they are. **Exclude today's planned items** is on by default, so today's queue on the shop floor is not reshuffled. **Response time for planned start (days)** is filled in from the admin setting, and a change here applies to this run only. It is added after a supplier's delivery and after the raw material arrives, not after a step done in house. Every run ends by replanning all dates, also a run that moves nothing.

Only one run can be in progress at a time. While someone else's run is going, the dialog shows who started it and when, and **Run Auto-Plan** stays disabled until that run has finished. If you close the dialog during your own run, the run continues in the background, and the button shows a spinning icon until it ends.

## Reading the result {#result}

The result table lists every order the run moved, with its machine or pool and its window **Before** and **After**, and any conflict it now has. Below the table two counts name the orders left alone on purpose: pinned or running orders, and orders already planned for today.

Orders the run could not place are listed separately with a reason. **Waiting on material** means the raw material has neither arrived nor been ordered with a delivery date. **No eligible machine** and **No eligible pool** mean nothing in the run can do the work. **No pool member in scope** means a capable pool exists but none of its machines was ticked. **Machine down** means a capable machine exists but has an open downtime, so the run left it out. **Changed while planning** means someone changed that queue during the run, so run Auto-Plan again to place the order.

**Re-dated by the Schedule Walk** lists the orders the run did not place but whose day changed when the dates were replanned, such as a manual step that can start today or a step after a late delivery. Each row shows **Before** and **After**, the **Shift** in days and the **Reason** the date has now. **All**, **Earlier** and **Later** filter the list, a click on a row opens the order, and a line below counts the orders that kept their day. When the replanning failed, a notice says so, and the dates follow with the next replanning.

## Planning level {#planning-level}

The planning level decides how far the run goes with an order that is not on a machine yet.

**Pools** is preselected. The run never picks a machine, and an order already on a machine stays where it is. The run may move a pool order to another capable pool and gives an order without a machine or pool a pool. The shop floor picks the machine later, when the order is started.

**Machines** treats an order already on a machine as **Allow assigning machines** says, and places a pool order on the member of its own pool that finishes it soonest, behind the work already queued there. An order with neither machine nor pool gets a machine only when **Allow assigning machines** is on.

## The six algorithms {#algorithms}

Each algorithm pairs one rule for the order in which candidates are considered with one rule for picking the machine. The same data with the same options always gives the same plan. When you open this page from the dialog, the algorithm you picked is marked.

<AutoPlanAlgorithmCards />
