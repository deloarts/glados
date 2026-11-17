---
title: Statusübergänge eines Rohblock-Bedarfs
summary: Jede Statusänderung eines Rohblock-Bedarfs, was sie auslöst und was sie sonst noch ändert.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py
  - backend/src/read/domain/services/state_machine_catalog.py
  - backend/tests/unit/lifecycle/test_state_transitions.py
lastVerified: 2026-10-26
---

<script setup lang="ts">
import StateTransitionsEmbed from '@/features/handbook/state-machines/components/StateTransitionsEmbed.vue'
</script>

Ein Rohblock-Bedarf, das Rohmaterial eines Loses, ergibt sich aus seinen Zuteilungen, dem, was auf ihnen geliefert wurde, und dem, was aus dem Lager genommen wurde. Die Status beschreibt [Lebenszyklus eines Rohblock-Bedarfs](/handbook/procurement/source-item-demand-lifecycle).

<StateTransitionsEmbed machine-key="source_item_demand_status" />

Die Zeilen sind nicht von Hand geschrieben. Ein Test lässt die echten Aktionen aller Lebenszyklen gegeneinander laufen und schlägt fehl, wenn das System eine Änderung macht, die diese Seite nicht nennt, oder die Seite eine nennt, die das System nicht machen kann. So zeigt die Seite immer, was das System tut.
