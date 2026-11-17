---
title: Statusübergänge eines Loses
summary: Jede Statusänderung eines Loses, was sie auslöst und was sie sonst noch ändert.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py
  - backend/src/read/domain/services/state_machine_catalog.py
  - backend/tests/unit/lifecycle/test_state_transitions.py
lastVerified: 2026-10-26
---

<script setup lang="ts">
import StateTransitionsEmbed from '@/features/handbook/state-machines/components/StateTransitionsEmbed.vue'
</script>

Der Status eines Loses ergibt sich aus seinen Positionen und aus den Aktionen am Los. Die Tabelle zeigt jede Änderung, die das System macht, die Aktion oder gebuchte Tatsache, die sie auslöst, die Zeilen der [Entscheidungstabelle des Loses](/handbook/production/lot-lifecycle), die den neuen Status ergeben, und was dieselbe Aktion an Positionen, Fertigungsaufträgen, Bestellpositionen und Bedarfen des Loses ändert.

<StateTransitionsEmbed machine-key="lot_status" />

Die Zeilen sind nicht von Hand geschrieben. Ein Test lässt die echten Aktionen aller Lebenszyklen gegeneinander laufen und schlägt fehl, wenn das System eine Änderung macht, die diese Seite nicht nennt, oder die Seite eine nennt, die das System nicht machen kann. So zeigt die Seite immer, was das System tut.
