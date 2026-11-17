---
title: Made Item Demand Lifecycle
summary: How a project's need for a made item moves from open through allocation and lot planning to fulfilled, and what canceling it takes down.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/demand.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/domain/services/demand_status_rules.py
  - backend/src/modules/fulfillment/application/use_cases/made_item_demand/cancel_demand.py
  - backend/src/modules/fulfillment/application/use_cases/made_item_demand/update_demand_item_status.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

A made item demand is one project's need for a part made in house, a row in the **Made Items Demand** list. Its status follows the same rules as a [bought item demand](/handbook/procurement/bought-item-demand-lifecycle), but nothing here is bought from a supplier: a production lot covers it, and the lot's progress counts as delivery. The diagram below is read live from the rules the system runs.

<StateMachineEmbed machine-key="made_item_demand_status" />

## What each status means

**Open** has nothing allocated. **Allocated** means something is allocated, from stock or from a lot, but the demand is not yet fully covered and placed, so the rest stays visible to **Auto-Assign**, see [Auto-Assigning Lots](/handbook/procurement/made-item-auto-assign). **Ordered** means the allocations and stock cover the whole quantity and every lot behind it has left **Draft** in the [lot lifecycle](/handbook/production/lot-lifecycle) and is neither canceled nor scrapped. A held lot counts too, because planning the lot is the commitment. **Fulfilled** is reached once the pieces its lots completed plus stock cover the quantity, which stock alone can do in one step from Open, or when someone marks the demand fulfilled by hand. **Canceled** is the other end. A demand also moves backward when what covers it comes undone, for example when a lot is canceled or an allocation removed.

## How completed pieces are shared

When one lot covers several demands, the pieces it completes go to them in a fixed order, the oldest demand first, so the first demand is fulfilled as soon as its own pieces are done while the next one waits for the pieces after them. When scrap or rework shrinks the lot, the demands give up pieces in the opposite order, starting with the newest one, and a demand that is already fulfilled only after every open one. The pieces they give up move to the replacement or rework lot when one is created.

## Setting a status by hand

You set only two statuses by hand, **Fulfilled** and **Canceled**, through **Set Status** in the row menu or the status buttons in the demand dialog. Both need **Write Demand Items** and **Manage Demand Items**; without them the buttons show disabled and the tooltip names the missing permission. Marking a demand fulfilled leaves its lots as they are, so they keep producing and their pieces stay allocated to it.

Canceling first shows what goes with it: the lots built only for this demand are canceled with their production orders, supplier lines and raw material demands, a lot shared with other demands only loses this demand's share, and the stock allocation is released. When lots cover the demand, this also needs **Manage Production Lots**. A lot built only for this demand that already has good pieces is not canceled, so the cancel is refused: force-complete that lot with **Complete Lot** first, see [Lot Lifecycle](/handbook/production/lot-lifecycle), and then cancel the demand. A fulfilled or canceled demand takes neither action again and can no longer be edited. Every action is listed in [Made Item Demand Transitions](/handbook/procurement/made-item-demand-transitions).

## Examples

**A lot for two demands.** One lot of 12 brackets covers demand 201 with 8 and demand 204 with 4. The first 8 good pieces fulfil demand 201, and demand 204 is fulfilled with the last 4.

**Canceling before production.** A demand for 5 shafts has its own planned lot, and nothing is made yet. The **Cancel Demand** dialog lists the lot and its production orders as canceled, and you confirm.

**A cancel that is refused.** The same lot has already finished 2 good shafts. The cancel is refused, so you force-complete the lot at 2 and cancel the demand afterwards.
