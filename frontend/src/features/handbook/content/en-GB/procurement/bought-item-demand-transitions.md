---
title: Bought Item Demand Transitions
summary: Every status change of a bought item demand, what triggers it and what else it changes.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py
  - backend/src/read/domain/services/state_machine_catalog.py
  - backend/tests/unit/lifecycle/test_state_transitions.py
lastVerified: 2026-10-26
---

<script setup lang="ts">
import StateTransitionsEmbed from '@/features/handbook/state-machines/components/StateTransitionsEmbed.vue'
</script>

A bought item demand's status follows from its allocations, what arrived on them and what was taken from stock. The statuses are described in [Bought Item Demand Lifecycle](/handbook/procurement/bought-item-demand-lifecycle).

<StateTransitionsEmbed machine-key="bought_item_demand_status" />

The rows are not written by hand. A test runs the real actions of every lifecycle against each other and fails when the system makes a change this page does not list, or when the page lists one the system cannot make, so the page always matches what the system does.
