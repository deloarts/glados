---
title: Lot Lifecycle
summary: How a lot's status follows from its positions and from the actions taken on it, and what holding, force-completing, canceling and scrapping do.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/lot.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/lot_lifecycle.py
  - backend/src/modules/fulfillment/application/services/lot_cascades.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/update_lot.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/notifications.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

A lot's status is never set directly. It follows from its positions, described on [Lot Position Status](/handbook/production/lot-position-lifecycle), and from the actions taken on the lot itself. The table is read live from the rules the system runs, and the first row that applies sets the status.

<StateMachineEmbed machine-key="lot_status" />

## How the status follows {#status}

A new lot starts in **Draft** and moves through **Partially Planned** and **Planned** as its positions are committed, before any work happens. **In Progress** means real production is under way. A lot is **Completed** once every position is completed. While a lot is a draft you can change its quantity, never below what made item demands have allocated to it. A supplier line not ordered yet shrinks with its position, and the raw material demand follows in proportion. The change is refused when that demand is already allocated or ordered, or when the new quantity gives no whole number of counted pieces.

## Putting a lot on hold {#hold}

**Put on Hold** is offered on a lot that is Partially Planned, Planned or In Progress, and asks for a **Reason**. It pauses the lot's running production orders. While the lot is held, none of its orders can be started or resumed, and no completion, scrap or reversal is booked on them, but deliveries and ordering its supplier lines still go through. **Resume** continues exactly the orders the hold paused, and an order you paused yourself stays paused. A held lot still completes when its last pieces are done. Both actions need **Write Production Lots**.

## Ending a lot early {#end}

**Complete Lot** closes a lot short when it cannot be finished. It needs a good piece at any position and **Manage Production Lots**. The lot shrinks to what its last position produced, the good pieces waiting between positions are recorded as dropped, each production order ends at what it processed or is canceled when it processed nothing, and the lot's demands are reduced to match. Nothing is booked as delivered that did not arrive.

**Cancel Lot** ends the lot and cancels its open work, as long as no position has a good piece yet, and also needs **Manage Production Lots**. A lot with good pieces is completed with **Complete Lot** instead. Supplier lines not ordered yet are canceled, a partly delivered line is closed short, and an ordered line that received nothing stays open so purchasing can settle it with the supplier. Neither action can be undone.

## What happens to the raw material {#material}

Both actions settle the lot's raw material demand. If nothing of it was ordered or taken from stock, it is canceled. Otherwise it is fulfilled at what arrived, and the part of its supplier lines that has not arrived is released. Everyone with **Write Orders** gets a notification, and a mail when mail is set up, naming the supplier lines left to settle.

## Scrapped lots {#scrapped}

**Scrap Pieces** removes pieces from a step whose production order is running, with a **Reason**. It is not offered on a held lot. By default it creates a replacement lot for the scrapped pieces. If you untick **Create replacement lot**, the lot's demands are simply covered by fewer pieces. Everyone with **Manage Production Lots** is notified. A lot whose quantity reaches zero this way is **Scrapped**.

## Material source {#source}

A lot whose source item needs approval waits until the source is approved, and its raw material demand is created then. Approving, rejecting and switching the source are explained on [Material Source](/handbook/production/material-source).
