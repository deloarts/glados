---
title: Quote Request Transitions
summary: Every status change of a quote request, what triggers it and what else it changes.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py
  - backend/src/read/domain/services/state_machine_catalog.py
  - backend/tests/unit/lifecycle/test_state_transitions.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateTransitionsEmbed from '@/features/handbook/state-machines/components/StateTransitionsEmbed.vue'
</script>

A quote request's status follows from what was done to it and from the state of its lines. The table lists each change, the action behind it and what the same action changes elsewhere, such as the order lines an award creates. The statuses are described in [Quote Requests](/handbook/procurement/quotes).

<StateTransitionsEmbed machine-key="quote_request_status" />

The rows are not written by hand. A test runs the real actions of every lifecycle against each other and fails when the system makes a change this page does not list, or when the page lists one the system cannot make, so the page always matches what the system does.
