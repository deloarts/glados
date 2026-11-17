---
title: Bought Item Demand Lifecycle
summary: How a project's need for a bought item moves from open through allocation and ordering to fulfilled, and the two statuses you set by hand.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/demand.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/domain/services/demand_status_rules.py
  - backend/src/modules/fulfillment/application/use_cases/_demand_family/update_status.py
  - backend/src/modules/fulfillment/application/use_cases/bought_item_demand/cancel_demand_item.py
  - frontend/src/features/procurement/utils/demandDisplayStatus.ts
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

A bought item demand is one project's need for a purchased part, a row in the **Bought Items Demand** list, tracked independently of any one order. Its status is worked out from its allocations and the order lines behind them every time one of them changes. The diagram below is read live from the rules the system runs.

<StateMachineEmbed machine-key="bought_item_demand_status" />

## What each status means

**Open** has nothing allocated. **Allocated** means something is allocated, from stock or from an order line, but the demand is not yet fully covered and placed, so the rest stays visible to **Auto-Allocate**. **Ordered** means the allocations and stock cover the whole quantity and every order line behind it is ordered or further along. **Fulfilled** is reached once the delivered pieces plus stock cover the quantity, which stock alone can do in one step from Open, or when someone marks the demand fulfilled by hand. **Canceled** is the other end. A demand also moves backward when what covers it comes undone, for example when a line is canceled or an allocation removed.

The table shows the same status in finer steps. **Partially Allocated** and **Partially Ordered** mark a demand that is only partly covered or partly ordered, and **Partially Delivered** one whose first pieces have arrived. How you cover a demand from orders and from stock is described in [Allocating Demands](/handbook/procurement/demand-allocations).

## How arriving pieces are shared

When one order line covers several demands, the pieces that arrive go to them in a fixed order: bought item demands first, then raw material demands, the oldest demand first in each. The first demand is fulfilled as soon as its own pieces are in, while the next one waits for the pieces after them. Only accepted pieces count. A piece written off as lost never arrives, so the line's allocations shrink to what it can still bring, starting with the newest demand, and the missing pieces show up on that demand again as Allocated or Open.

## Setting a status by hand

You set only two statuses by hand, **Fulfilled** and **Canceled**, through **Set Status** in the row menu or the status buttons in the demand dialog. Both need **Write Demand Items** and **Manage Demand Items**; without them the buttons show disabled and the tooltip names the missing permission. Canceling releases every allocation, on order lines and from stock, so the line capacity and the stock are free again. Marking a demand fulfilled asks first and keeps only what already arrived for it: the part of its order line allocations whose pieces have not arrived is released, so you can shrink those lines or allocate them to other demands. Stock allocations stay. A fulfilled or canceled demand takes neither action again, and it can no longer be edited. Until then you can change its note, dates and flags, and its quantity as long as it does not drop below what is already allocated. Every action with the statuses it starts from is listed in [Bought Item Demand Transitions](/handbook/procurement/bought-item-demand-transitions).

## Examples

**Covered from stock.** A demand for 10 relays is Open, and 10 are on the shelf. **Fulfill from Stock** with 10 moves it straight to Fulfilled.

**One line for two demands.** An order line for 30 covers demand 101 with 20 and demand 105 with 10. The first 20 pieces that arrive fulfil demand 101, and demand 105 waits for the last 10.

**Closing a demand early.** A demand for 8 has 5 delivered and 3 still on order. You mark it fulfilled, it keeps the 5, and the 3 on the line are released for another demand.
