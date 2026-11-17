---
title: Production Order Lifecycle
summary: What a production order's status means as it queues, runs, pauses and finishes on a machine, what a start needs, and how a completion is corrected.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/production_order.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/production_order_lifecycle.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/reverse_production_order_completion.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/split_production_order.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/merge_production_orders.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

A production order is one entry in a machine's queue, the in-house share of a lot position's work, created when [Manage Production](/handbook/production/manage-production) commits a position. Its status shows on the queue board, the machine's own page, the lot's step list, the WIP table and the order's own page. It follows from what was recorded on the order: its start, its pauses and its completions.

<StateMachineEmbed machine-key="production_order_status" />

## Statuses {#statuses}

**Queued** orders wait their turn. Starting an order makes it **In Progress** and records its actual start once, so a later resume does not move it. An order is **Completed** as soon as the pieces recorded on it reach its quantity. Accepted and rejected pieces both count, and rejects can only be booked on an inspection position. A completed order goes back to **In Progress** when one of its completions is reversed.

**Canceled** is the only final status. An order is canceled when someone cancels it, when its lot is canceled, when its lot is completed early before the order processed anything, when its made item demand is canceled, when it is merged into another order, when a supplier delivery covers its position, or when scrap leaves nothing for it to make. You can cancel your own orders with **Write Production Orders**, and other people's orders with **Manage Production Orders**.

## Pauses {#pauses}

**Paused** lasts exactly while an interruption is open, and there are two kinds. A pause you set on the order yourself ends when you resume the order. A pause that comes from putting the lot on hold ends only when the lot is resumed, see [Lot Lifecycle](/handbook/production/lot-lifecycle#hold). While the lot is held, its orders cannot be started or resumed, and they take no completion, scrap or reversal. Paused time does not count as work.

## Starting and resuming {#start}

An order can start only while its lot is not on hold and not finished, and only when pieces are available, from the previous step or, for the first step, from the raw material that has arrived. A pool order needs a machine, which the **Start Production Order** dialog asks for. Resuming your own pause needs the same pieces and a lot that is not on hold. Starting, pausing and recording completions need **Write Production Orders**. How completions are recorded is described on [Recording Completions](/handbook/production/completions).

## Correcting a completion {#reverse}

A completion booked by mistake is taken back with **Reverse** on the lot page, which asks for a **Reason**. Both entries stay on record. This needs **Manage Production Orders**, and the button shows disabled with a tooltip without it. A completion can be reversed once, only when it rejected nothing, and only while the next position has not used its pieces. The lot must not be on hold or finished.

## Splitting and merging {#split}

A queued order can be split into two or more parts on the same machine with **Split**. Queued orders of the same lot position on the same machine and pool can be joined again with **Merge**, and the orders merged away are canceled.

## Examples {#examples}

An order of 40 is running. The operator records 30 pieces and then 10 more, and the order is **Completed**. The second booking was a mistake, so the operator reverses it with a reason, and the order is **In Progress** again with 30 pieces.

A lot is put on hold while one of its orders is running. The order is **Paused** and cannot be resumed on its own until the lot is resumed.
