---
title: Statusübergänge einer Losposition
summary: Jede Änderung von Status und Art einer Losposition, was sie auslöst und was sie sonst noch ändert.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/observed_transitions.py
  - backend/src/read/domain/services/state_machine_catalog.py
  - backend/tests/unit/lifecycle/test_state_transitions.py
lastVerified: 2026-10-26
---

<script setup lang="ts">
import StateTransitionsEmbed from '@/features/handbook/state-machines/components/StateTransitionsEmbed.vue'
</script>

Eine Losposition hat zwei abgeleitete Werte: ihren Status, aus der Arbeit an ihr, und ihre [Art](/handbook/production/lot-position-kind), daraus, wer sie fertigt. Die erste Tabelle zeigt die Statusänderungen, die zweite die Änderungen der Art.

<StateTransitionsEmbed machine-key="lot_position_status" />

<StateTransitionsEmbed machine-key="lot_position_kind" />

Die Zeilen sind nicht von Hand geschrieben. Ein Test lässt die echten Aktionen aller Lebenszyklen gegeneinander laufen und schlägt fehl, wenn das System eine Änderung macht, die diese Seite nicht nennt, oder die Seite eine nennt, die das System nicht machen kann. So zeigt die Seite immer, was das System tut.
