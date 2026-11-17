---
title: Production Order Transitions
summary: Every status change of a production order, what triggers it and what else it changes.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py
  - backend/src/read/domain/services/state_machine_catalog.py
  - backend/tests/unit/lifecycle/test_state_transitions.py
lastVerified: 2026-10-26
---

<script setup lang="ts">
import StateTransitionsEmbed from '@/features/handbook/state-machines/components/StateTransitionsEmbed.vue'
</script>

A production order's status follows from its start, its interruptions and its completions. The table lists each change, the action behind it with its condition and permission, and what the same action changes on the order's position and lot. The statuses themselves are described in [Production Order Lifecycle](/handbook/production/production-order-lifecycle).

<StateTransitionsEmbed machine-key="production_order_status" />

The rows are not written by hand. A test runs the real actions of every lifecycle against each other and fails when the system makes a change this page does not list, or when the page lists one the system cannot make, so the page always matches what the system does.
