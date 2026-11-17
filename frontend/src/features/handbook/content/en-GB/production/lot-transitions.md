---
title: Lot Transitions
summary: Every status change of a lot, what triggers it and what else it changes.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py
  - backend/src/read/domain/services/state_machine_catalog.py
  - backend/tests/unit/lifecycle/test_state_transitions.py
lastVerified: 2026-10-26
---

<script setup lang="ts">
import StateTransitionsEmbed from '@/features/handbook/state-machines/components/StateTransitionsEmbed.vue'
</script>

A lot's status follows from its positions and from the actions taken on the lot. The table lists each change the system makes, the action or recorded fact that triggers it, the rows of the [lot's decision table](/handbook/production/lot-lifecycle) that give the new status, and what the same action changes on the lot's positions, production orders, lines and demands.

<StateTransitionsEmbed machine-key="lot_status" />

The rows are not written by hand. A test runs the real actions of every lifecycle against each other and fails when the system makes a change this page does not list, or when the page lists one the system cannot make, so the page always matches what the system does.
