---
title: Lot Position Transitions
summary: Every change of a lot position's status and kind, what triggers it and what else it changes.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py
  - backend/src/read/domain/services/state_machine_catalog.py
  - backend/tests/unit/lifecycle/test_state_transitions.py
lastVerified: 2026-10-26
---

<script setup lang="ts">
import StateTransitionsEmbed from '@/features/handbook/state-machines/components/StateTransitionsEmbed.vue'
</script>

A lot position has two derived values: its status, from the work on it, and its [kind](/handbook/production/lot-position-kind), from who makes it. The first table lists the status changes, the second the changes of the kind.

<StateTransitionsEmbed machine-key="lot_position_status" />

<StateTransitionsEmbed machine-key="lot_position_kind" />

The rows are not written by hand. A test runs the real actions of every lifecycle against each other and fails when the system makes a change this page does not list, or when the page lists one the system cannot make, so the page always matches what the system does.
