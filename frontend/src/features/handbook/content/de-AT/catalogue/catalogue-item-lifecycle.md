---
title: Lebenszyklus eines Katalogartikels
summary: Was Aktiv, Inaktiv und Ersetzt für ein Zukaufteil, Fertigungsteil oder einen Rohblock bedeuten, wie du einen Artikel zwischen ihnen bewegst und was ein Nachfolger bewirkt.
sourceRefs:
  - backend/src/modules/catalogue/domain/policies/catalogue_item_status.py
  - backend/src/modules/catalogue/domain/policies/pdm_ownership.py
  - backend/src/read/domain/services/state_machine_catalog.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

Jedes Zukaufteil, Fertigungsteil und jeder Rohblock hat einen von drei Status, und die drei Kataloge teilen dieselben Regeln. Nichts leitet den Status für dich ab: Er sagt, ob der Artikel noch für neue Arbeit verwendet werden darf. Das Diagramm unten wird live aus den Regeln gelesen, nach denen das System arbeitet.

<StateMachineEmbed machine-key="catalogue_item_status" />

## Was jeder Status bedeutet

**Aktiv** ist der Normalfall. Ein neuer Bedarf, ein neues Los, eine neue Bestellposition oder ein Ersatz darf einen Artikel nur nennen, solange er aktiv und nicht archiviert ist und, bei einem Artikel aus PDM, nicht **Fehlt im Vault** zeigt. **Inaktiv** lässt den Artikel im Katalog, nimmt ihn aber aus neuer Arbeit heraus. **Ersetzt** macht dasselbe und nennt einen **Nachfolgeartikel**, der seinen Platz einnimmt. Wählst du einen ersetzten Artikel für einen neuen Bedarf, sagt der Dialog „Der ausgewählte Artikel wurde durch einen anderen Artikel ersetzt." und bietet **Ersatzartikel verwenden** an. Arbeit, die einen Artikel schon nennt, läuft weiter, egal welchen Status er bekommt, eine Statusänderung hält also nie ein laufendes Los oder eine offene Bestellposition an.

## Den Status ändern

Du änderst den Status über **Status** im Bearbeiten-Dialog des Artikels, wofür du die Schreibberechtigung dieses Katalogs brauchst, zum Beispiel **Zukaufteile schreiben**. Ein Wechsel auf **Ersetzt** braucht einen Nachfolger aus demselben Katalog, der existiert, nicht archiviert ist und nicht auf den Artikel zurückführt. Ein Wechsel auf **Aktiv** oder **Inaktiv** entfernt den Nachfolger. Bei einer älteren Revision eines Fertigungsteils lässt sich nur der Status ändern, und **Neue Revision** setzt den Status der aktuellen Revision für dich.

Bei einem Artikel aus PDM folgt der Status dem Workflow-Zustand seiner Datei, das Feld ist also gesperrt und sagt „Der Status wird von PDM verwaltet. Verschiebe die Datei in PDM zuerst in einen Ersetzt-Zustand, bevor du einen Nachfolger festlegst." Den Nachfolger selbst setzt weiter du, sobald PDM den Artikel als ersetzt markiert hat.

Archivieren ist vom Status getrennt. **Archivieren** blendet den Artikel aus den Listen aus, **Wiederherstellen** holt ihn zurück, und **Zusammenführen** archiviert den Artikel, der zusammengeführt wird.

## Beispiele

**Ein Teil läuft aus.** Der Hersteller stellt ein Relais ein. Du setzt es auf **Inaktiv**, und niemand kann mehr einen Bedarf dafür anlegen, während die offene Bestellung dafür noch geliefert wird.

**Ein neueres Teil ersetzt es.** Du setzt das alte Relais auf **Ersetzt** und wählst das neue als **Nachfolgeartikel**. Wer das alte Relais für einen Bedarf wählt, bekommt **Ersatzartikel verwenden** angeboten.

**Ein Teil aus PDM.** Die Konstruktion verschiebt die Datei in PDM in einen Ersetzt-Zustand. Nach der nächsten Synchronisation steht der Artikel auf **Ersetzt**, und du wählst seinen Nachfolger im Bearbeiten-Dialog.
