---
title: Lot Position Status
summary: How the status of a lot position follows from its supplier lines and production orders, and why the same status reads differently on internal and external steps.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/lot_position.py
  - backend/src/modules/fulfillment/domain/services/lot_rules.py
  - frontend/src/features/production/utils/lotStatus.ts
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

Every step of a lot belongs to a position, and the position's status is what the lots table and the lot page show for that step. Nobody sets it. It follows from the supplier line on the position, put there with [Manage Orders](/handbook/production/manage-orders), and from its production orders, put there with [Manage Production](/handbook/production/manage-production). The lot's own status then follows from all its positions, see [Lot Lifecycle](/handbook/production/lot-lifecycle).

<StateMachineEmbed machine-key="lot_position_status" />

## How the status is worked out {#statuses}

The rows of the table are checked from the top, and the first one that applies sets the status. A position of a canceled lot is **Canceled**. A position whose completed pieces reach its quantity is **Completed**, and one with some completed pieces is **Partially Completed**. A position with a production order running or paused is **In Progress**. A supplier gives no start signal, so a purely external position skips this status. A position whose supplier line is ordered or partly delivered, or which has a queued production order, is ordered or queued. Everything else is pending.

## What the step shows {#labels}

The kind of the position decides how the last two statuses read, because an internal position can only be queued and an external one only ordered. A queued internal position shows **Queued**, an ordered external one **Ordered**, and only a mixed one shows **Ordered / Queued**. A pending external or mixed position shows **Allocated**, because a supplier line exists that purchasing has not ordered yet. A pending unassigned or internal position shows **Pending**. The kind itself is explained on [Lot Position Kind](/handbook/production/lot-position-kind).

## After the order is placed {#after}

Assigning a step to a supplier records the intent, and marking its line ordered records the commitment. Only then does the step move to **Ordered**, and the lot usually moves to Partially Planned or Planned. Each delivery adds its pieces to the position's completed count. On a mixed position, the delivered pieces and the pieces made in-house add up, so neither side overwrites the other. A delivery cannot count more pieces than the previous step has made. On a mixed first step, the in-house share is also limited by the raw material that has arrived.

## Splitting a position {#mixed}

A position can go partly to a supplier and partly to the shop floor. Both sides draw from the same remaining pieces, so a position of 100 with 30 ordered externally leaves 70 for Manage Production. A canceled production order gives back the pieces it had not made yet, and the pieces it made stay counted. A supplier line gives back nothing until it is removed or canceled.

## Examples {#examples}

You put a deburring step of 50 pieces on a draft order. The step shows **Allocated**. Purchasing sends the order and marks the line ordered, and the step shows **Ordered**. The supplier delivers 20, and the step shows **Partially Completed**.

A position of 10 has 4 pieces on a supplier line and 6 queued on a machine. Before anything is ordered or started it shows **Ordered / Queued**, because its production order is queued.
