---
title: Statusübergänge eines Fertigungsauftrags
summary: Jede Statusänderung eines Fertigungsauftrags, was sie auslöst und was sie sonst noch ändert.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py
  - backend/src/read/domain/services/state_machine_catalog.py
  - backend/tests/unit/lifecycle/test_state_transitions.py
lastVerified: 2026-10-26
---

<script setup lang="ts">
import StateTransitionsEmbed from '@/features/handbook/state-machines/components/StateTransitionsEmbed.vue'
</script>

Der Status eines Fertigungsauftrags ergibt sich aus seinem Start, seinen Unterbrechungen und seinen Fertigmeldungen. Die Tabelle zeigt jede Änderung, die Aktion dahinter mit Bedingung und Berechtigung, und was dieselbe Aktion an Position und Los des Auftrags ändert. Die Status selbst beschreibt [Lebenszyklus eines Fertigungsauftrags](/handbook/production/production-order-lifecycle).

<StateTransitionsEmbed machine-key="production_order_status" />

Die Zeilen sind nicht von Hand geschrieben. Ein Test lässt die echten Aktionen aller Lebenszyklen gegeneinander laufen und schlägt fehl, wenn das System eine Änderung macht, die diese Seite nicht nennt, oder die Seite eine nennt, die das System nicht machen kann. So zeigt die Seite immer, was das System tut.
