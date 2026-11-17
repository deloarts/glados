---
title: Status Cascades
summary: What an action on one record changes on the others, across lots, positions, production orders, orders, lines and demands.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py
  - backend/src/read/domain/services/state_machine_catalog.py
  - backend/tests/unit/lifecycle/test_state_transitions.py
lastVerified: 2026-10-26
---

<script setup lang="ts">
import StateTransitionsEmbed from '@/features/handbook/state-machines/components/StateTransitionsEmbed.vue'
</script>

An action never changes only the record it is taken on. Booking a receipt moves the line, its order, the demands allocated to it and, for a supplier line of a lot, the lot's position and the lot. The table lists, for every action, the status changes it can make on other records. Each lifecycle's own transitions are listed on its page, for example [Lot Transitions](/handbook/production/lot-transitions) and [Order Line Transitions](/handbook/procurement/order-line-transitions).

<StateTransitionsEmbed cascades />

The rows are not written by hand. A test runs the real actions of every lifecycle against each other and fails when the system makes a change this page does not list, or when the page lists one the system cannot make, so the page always matches what the system does.
