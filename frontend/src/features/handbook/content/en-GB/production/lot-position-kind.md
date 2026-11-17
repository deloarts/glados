---
title: Lot Position Kind
summary: The classifier behind a position's badge, unassigned, external, internal or mixed, how it follows from the work committed on the position, and why it has no end state.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/lot_position.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/assign_external_position.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/assign_internal_position.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

Kind is the badge shown next to a lot position in the lot page's step list, its position cards and Manage mode, the WIP table and the waiting time panel of the KPIs, and answers one question: who is doing this step. It is a different thing from a position's status, described on [Lot Position Status](/handbook/production/lot-position-lifecycle). Kind says who is on the hook, and status says how far they have got. The kind also changes how the status reads: a pending external or mixed step shows **Allocated**, an ordered external one **Ordered**, a queued internal one **Queued**, and only a mixed one **Ordered / Queued**. Nobody sets the kind, it is worked out from the work committed on the position.

<StateMachineEmbed machine-key="lot_position_kind" />

**Unassigned** is where every position starts, with nothing committed yet. A live supplier order line on the position, put there with [Manage Orders](/handbook/production/manage-orders), makes it **External**. A live production order from [Manage Production](/handbook/production/manage-production), or pieces already made in-house, make it **Internal**, and both sides together make it **Mixed**, part bought in, part made in-house. A canceled line or a canceled production order no longer counts, but the pieces a canceled production order made before it was canceled still do. Undoing a commitment therefore moves back the same way: removing or canceling the line falls back to Internal when in-house work or pieces remain, otherwise to Unassigned, and canceling the in-house side falls back to External as long as it made nothing. A supplier line that was closed short still counts as live, so the position stays External or Mixed, and a new line for the rest can be added beside it. A position of 10 with 4 ordered from a supplier and 6 planned on a machine is Mixed. Cancel the supplier line before anything arrives and it is Internal.

Notice there is no end state here. Kind is not a lifecycle with an end, it is a live classification worked out from what is committed right now, and the rows above show that in the order the system checks them.
