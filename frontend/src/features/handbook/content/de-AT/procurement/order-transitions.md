---
title: Statusübergänge einer Bestellung
summary: Jede Statusänderung einer Bestellung, was sie auslöst und was sie sonst noch ändert.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py
  - backend/src/read/domain/services/state_machine_catalog.py
  - backend/tests/unit/lifecycle/test_state_transitions.py
lastVerified: 2026-10-26
---

<script setup lang="ts">
import StateTransitionsEmbed from '@/features/handbook/state-machines/components/StateTransitionsEmbed.vue'
</script>

Der Status einer Bestellung ergibt sich aus ihren Positionen. Die Tabelle zeigt jede Änderung, die Aktion dahinter und was dieselbe Aktion an den Positionen und an den Bedarfen und Lospositionen ändert, denen sie dienen. Die Status beschreibt [Lebenszyklus einer Bestellung](/handbook/procurement/order-lifecycle).

<StateTransitionsEmbed machine-key="order_status" />

Die Zeilen sind nicht von Hand geschrieben. Ein Test lässt die echten Aktionen aller Lebenszyklen gegeneinander laufen und schlägt fehl, wenn das System eine Änderung macht, die diese Seite nicht nennt, oder die Seite eine nennt, die das System nicht machen kann. So zeigt die Seite immer, was das System tut.
