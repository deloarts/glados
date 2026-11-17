---
title: Statusübergänge einer Angebotsanfrage
summary: Jede Statusänderung einer Angebotsanfrage, was sie auslöst und was sie sonst noch ändert.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py
  - backend/src/read/domain/services/state_machine_catalog.py
  - backend/tests/unit/lifecycle/test_state_transitions.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateTransitionsEmbed from '@/features/handbook/state-machines/components/StateTransitionsEmbed.vue'
</script>

Der Status einer Angebotsanfrage ergibt sich aus dem, was mit ihr gemacht wurde, und aus dem Zustand ihrer Positionen. Die Tabelle zeigt jede Änderung, die Aktion dahinter und was dieselbe Aktion sonst noch ändert, etwa die Bestellpositionen, die eine Vergabe anlegt. Die Status beschreibt [Angebotsanfragen](/handbook/procurement/quotes).

<StateTransitionsEmbed machine-key="quote_request_status" />

Die Zeilen sind nicht von Hand geschrieben. Ein Test lässt die echten Aktionen aller Lebenszyklen gegeneinander laufen und schlägt fehl, wenn das System eine Änderung macht, die diese Seite nicht nennt, oder die Seite eine nennt, die das System nicht machen kann. So zeigt die Seite immer, was das System tut.
