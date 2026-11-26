---
title: So funktioniert Auto-Planen
summary: Wie du Auto-Planen startest, wie du das Ergebnis liest, was die Planungsebene ändert und wie sich die sechs Algorithmen unterscheiden.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_schedule/auto_plan.py
  - backend/src/modules/fulfillment/domain/value_objects/auto_plan_algorithm.py
  - frontend/src/features/production/components/AutoPlanDialog.vue
  - backend/src/modules/fulfillment/application/use_cases/production_schedule/_redated.py
lastVerified: 2026-11-26
---

<script setup lang="ts">
import AutoPlanAlgorithmCards from '@/features/production/planning/components/AutoPlanAlgorithmCards.vue'
</script>

Auto-Planen baut die Maschinenwarteschlangen in einem Durchlauf neu auf. Es sortiert die wartenden Aufträge, die es bewegen darf, nach dem gewählten Algorithmus und legt jeden auf eine Maschine oder einen Pool, rund um die Aufträge, die es nicht anrühren darf. Die Regeln dahinter stehen unter [So plant Auto-Planen Aufträge ein](/handbook/production/auto-plan-rules) und [Wann ein Auftrag starten kann](/handbook/production/auto-plan-timing).

<Message severity="warn" :closable="false">
Auto-Planen schreibt sein Ergebnis sofort. Es gibt keine Vorschau und keinen Bestätigungsschritt, und die Tabelle danach zeigt, was bereits geändert wurde.
</Message>

## Ausführen {#run}

Du öffnest Auto-Planen mit dem Button **Auto-Planen** im Tab Lose oder im Tab Kapazität. Der Button braucht **Fertigungsaufträge schreiben** und ist ohne diese Berechtigung deaktiviert, mit einem Tooltip. Im Dialog wählst du den **Planungsalgorithmus** und die **Planungsebene**, und unter **Einzubeziehende Maschinen** nimmst du das Häkchen bei jeder Maschine weg, die der Lauf in Ruhe lassen soll. **Maschinenzuweisung erlauben** ist standardmäßig aus, ein Auftrag bewegt sich also nur innerhalb seiner Maschine. **Überschreiben von manuell geplanten Terminen erlauben** ist standardmäßig aus, angeheftete Aufträge bleiben also, wo sie sind. **Heute geplante Aufträge ausschließen** ist standardmäßig an, damit die heutige Warteschlange in der Werkstatt nicht durcheinanderkommt. **Reaktionszeit für geplanten Start (Tage)** ist aus der Admin-Einstellung vorbefüllt, und eine Änderung hier gilt nur für diesen Lauf. Sie kommt nach der Lieferung eines Lieferanten und nach der Ankunft des Rohmaterials dazu, nicht nach einem Schritt in der Eigenfertigung. Jeder Lauf plant am Ende alle Termine neu, auch ein Lauf, der nichts verschiebt.

Es kann immer nur ein Lauf gleichzeitig laufen. Während der Lauf eines anderen läuft, zeigt der Dialog, wer ihn wann gestartet hat, und **Auto-Plan ausführen** bleibt deaktiviert, bis dieser Lauf fertig ist. Schließt du den Dialog während deines eigenen Laufs, läuft der Lauf im Hintergrund weiter, und der Button zeigt ein drehendes Symbol, bis er endet.

## Das Ergebnis lesen {#result}

Die Ergebnistabelle zeigt jeden Auftrag, den der Lauf verschoben hat, mit Maschine oder Pool und Zeitfenster **Vorher** und **Nachher**, und jeden Konflikt, den er jetzt hat. Unter der Tabelle nennen zwei Zahlen die Aufträge, die absichtlich unangetastet blieben: angeheftete oder laufende Aufträge und Aufträge, die schon für heute geplant sind.

Aufträge, die der Lauf nicht einplanen konnte, stehen getrennt mit einem Grund darunter. **Wartet auf Material** heißt, das Rohmaterial ist weder eingetroffen noch mit einem Liefertermin bestellt. **Keine geeignete Maschine** und **Kein geeigneter Pool** heißen, nichts im Lauf kann die Arbeit machen. **Kein Pool-Mitglied im Bereich** heißt, es gibt einen geeigneten Pool, aber keine seiner Maschinen war angehakt. **Maschine ausgefallen** heißt, eine geeignete Maschine gibt es, sie hat aber eine offene Ausfallzeit, daher hat der Lauf sie ausgelassen. **Während der Planung geändert** heißt, jemand hat diese Warteschlange während des Laufs geändert, starte Auto-Planen also erneut, um den Auftrag einzuplanen.

**Vom Terminlauf neu datiert** listet die Aufträge, die der Lauf nicht eingeplant hat, deren Tag sich beim Neuplanen der Termine aber geändert hat, etwa ein manueller Schritt, der heute beginnen kann, oder ein Schritt nach einer verspäteten Lieferung. Jede Zeile zeigt **Vorher** und **Nachher**, die **Verschiebung** in Tagen und den **Grund** für den neuen Termin. **Alle**, **Früher** und **Später** filtern die Liste, ein Klick auf eine Zeile öffnet den Auftrag, und eine Zeile darunter zählt die Aufträge, die ihren Tag behalten haben. Ist das Neuplanen fehlgeschlagen, sagt das ein Hinweis, und die Termine folgen mit dem nächsten Neuplanen.

## Planungsebene {#planning-level}

Die Planungsebene entscheidet, wie weit der Lauf bei einem Auftrag geht, der noch auf keiner Maschine liegt.

**Pools** ist vorausgewählt. Der Lauf wählt nie eine Maschine, und ein Auftrag, der schon auf einer Maschine liegt, bleibt, wo er ist. Der Lauf darf einen Poolauftrag in einen anderen geeigneten Pool verschieben und gibt einem Auftrag ohne Maschine und ohne Pool einen Pool. Die Werkstatt wählt die Maschine später, wenn der Auftrag gestartet wird.

**Maschinen** behandelt einen Auftrag, der schon auf einer Maschine liegt, so, wie **Maschinenzuweisung erlauben** es sagt, und legt einen Poolauftrag auf jene Maschine seines eigenen Pools, die ihn am schnellsten fertigstellt, hinter die Arbeit, die dort schon wartet. Ein Auftrag ohne Maschine und ohne Pool bekommt nur dann eine Maschine, wenn **Maschinenzuweisung erlauben** an ist.

## Die sechs Algorithmen {#algorithms}

Jeder Algorithmus verbindet eine Regel, in welcher Reihenfolge die Kandidaten betrachtet werden, mit einer Regel für die Wahl der Maschine. Dieselben Daten mit denselben Optionen ergeben immer denselben Plan. Öffnest du diese Seite aus dem Dialog, ist der gewählte Algorithmus markiert.

<AutoPlanAlgorithmCards />
