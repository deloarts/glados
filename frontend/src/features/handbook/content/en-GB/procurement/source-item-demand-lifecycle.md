---
title: Source Item Demand Lifecycle
summary: How a lot's need for a source item (raw material) appears, moves from open through allocation and ordering to fulfilled, and what canceling it does to the lot.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/demand.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/domain/services/demand_status_rules.py
  - backend/src/modules/fulfillment/application/use_cases/source_item_demand/cancel_source_item_demand.py
  - backend/src/modules/fulfillment/application/use_cases/source_item_demand/update_source_item_demand.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/approve_lot_source.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/switch_lot_material_source.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

A source item demand is the raw material a production lot needs, a row in the **Source Items Demand** list. It belongs to one lot and follows the rules of a [bought item demand](/handbook/procurement/bought-item-demand-lifecycle): its status is worked out from its allocations and the order lines behind them every time one of them changes. The diagram below is read live from the rules the system runs.

<StateMachineEmbed machine-key="source_item_demand_status" />

## When the demand appears

A lot gets its raw material demand when its material source is set, usually as soon as the lot is created from a made item with a material source. **New Demand** on this list creates one for a lot by hand and needs **Write Production Lots**. When your administrator turned on **Require Source Item Approval**, a lot sourced from a source item gets no demand until someone approves its material source, so a lot that waits for approval has no row here yet. A lot sourced from a bought item is never held back. How approval works is described in [Material Source](/handbook/production/material-source).

## What each status means

**Open**, **Allocated**, **Ordered**, **Fulfilled** and **Canceled** mean the same as on a bought item demand. When one order line covers bought item demands and raw material demands together, the bought item demands get the arriving pieces first.

## Setting a status by hand

You set only **Fulfilled** and **Canceled** by hand, through **Set Status**, which needs **Write Demand Items** and **Manage Demand Items**. **Cancel Demand** in the row menu and in the demand dialog needs **Write Production Lots** instead. Without the permission the action shows disabled and the tooltip names what is missing. Marking a demand fulfilled asks first, keeps what already arrived and releases the rest of its order line allocations. Until a demand is fulfilled or canceled you can edit it, and its quantity never drops below what is already allocated.

Canceling the raw material demand of a lot asks what should happen to the lot. **Cancel Lot Too** cancels the lot and its open work together with the demand, which also needs **Manage Production Lots**. **Cancel Only the Demand** unlinks the demand from its lot, which then waits on raw material without a demand. Once the lot has started production, the cancel is refused, because the lot already holds or uses that material: change the material source, or force-complete the lot.

Changing the material source of a lot whose raw material is already allocated or ordered first shows what arrived. What arrived stays with the lot, and the demand is marked fulfilled with it. Its allocations on order lines whose pieces have not arrived are released, so purchasing can cancel those lines or close them short, and the new source gets a demand for what is still missing. Every action is listed in [Source Item Demand Transitions](/handbook/procurement/source-item-demand-transitions).

## Examples

**A plain cancel.** A planned lot no longer needs its steel bar. You cancel the demand, choose **Cancel Lot Too**, and the lot and its demand end together.

**Another material.** A lot is still in planning and should use a different bar. You change its material source instead of canceling, and the old demand is replaced in one step.

**A started lot.** The first step has already run. The cancel is refused, so you change the material source, and what arrived stays with the lot.
