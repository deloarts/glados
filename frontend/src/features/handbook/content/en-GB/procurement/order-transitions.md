---
title: Order Transitions
summary: Every status change of an order, what triggers it and what else it changes.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py
  - backend/src/read/domain/services/state_machine_catalog.py
  - backend/tests/unit/lifecycle/test_state_transitions.py
lastVerified: 2026-10-26
---

<script setup lang="ts">
import StateTransitionsEmbed from '@/features/handbook/state-machines/components/StateTransitionsEmbed.vue'
</script>

An order's status follows from its lines. The table lists each change, the action behind it and what the same action changes on the lines and on the demands and lot positions they serve. The statuses are described in [Order Lifecycle](/handbook/procurement/order-lifecycle).

<StateTransitionsEmbed machine-key="order_status" />

The rows are not written by hand. A test runs the real actions of every lifecycle against each other and fails when the system makes a change this page does not list, or when the page lists one the system cannot make, so the page always matches what the system does.
