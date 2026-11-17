---
title: Statuskaskaden
summary: Was eine Aktion an einem Datensatz an den anderen ändert, über Lose, Positionen, Fertigungsaufträge, Bestellungen, Bestellpositionen und Bedarfe.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py
  - backend/src/read/domain/services/state_machine_catalog.py
  - backend/tests/unit/lifecycle/test_state_transitions.py
lastVerified: 2026-10-26
---

<script setup lang="ts">
import StateTransitionsEmbed from '@/features/handbook/state-machines/components/StateTransitionsEmbed.vue'
</script>

Eine Aktion ändert nie nur den Datensatz, an dem sie ausgeführt wird. Ein gebuchter Wareneingang bewegt die Bestellposition, ihre Bestellung, die ihr zugeteilten Bedarfe und, bei einer Lieferantenposition eines Loses, die Losposition und das Los. Die Tabelle zeigt für jede Aktion die Statusänderungen, die sie an anderen Datensätzen machen kann. Die eigenen Übergänge jedes Lebenszyklus stehen auf seiner Seite, zum Beispiel [Statusübergänge eines Loses](/handbook/production/lot-transitions) und [Statusübergänge einer Bestellposition](/handbook/procurement/order-line-transitions).

<StateTransitionsEmbed cascades />

Die Zeilen sind nicht von Hand geschrieben. Ein Test lässt die echten Aktionen aller Lebenszyklen gegeneinander laufen und schlägt fehl, wenn das System eine Änderung macht, die diese Seite nicht nennt, oder die Seite eine nennt, die das System nicht machen kann. So zeigt die Seite immer, was das System tut.
