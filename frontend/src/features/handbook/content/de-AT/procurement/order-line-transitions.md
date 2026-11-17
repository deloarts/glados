---
title: Statusübergänge einer Bestellposition
summary: Jede Statusänderung einer Bestellposition, was sie auslöst und was sie sonst noch ändert.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py
  - backend/src/read/domain/services/state_machine_catalog.py
  - backend/tests/unit/lifecycle/test_state_transitions.py
lastVerified: 2026-10-26
---

<script setup lang="ts">
import StateTransitionsEmbed from '@/features/handbook/state-machines/components/StateTransitionsEmbed.vue'
</script>

Der Status einer Bestellposition ergibt sich daraus, was an ihr angefragt, bestellt und geliefert wurde. Die Tabelle zeigt jede Änderung, die Aktion dahinter mit Bedingung und Berechtigung, und was dieselbe Aktion an der Bestellung, ihren Bedarfen und, bei einer Lieferantenposition eines Loses, am Los ändert. Die Status beschreibt [Lebenszyklus einer Bestellung](/handbook/procurement/order-lifecycle).

<StateTransitionsEmbed machine-key="order_item_status" />

Die Zeilen sind nicht von Hand geschrieben. Ein Test lässt die echten Aktionen aller Lebenszyklen gegeneinander laufen und schlägt fehl, wenn das System eine Änderung macht, die diese Seite nicht nennt, oder die Seite eine nennt, die das System nicht machen kann. So zeigt die Seite immer, was das System tut.
