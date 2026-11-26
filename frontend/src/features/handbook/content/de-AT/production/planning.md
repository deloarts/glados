---
title: Planung
summary: Wie du das Gantt-Diagramm im Reiter Planung liest, woher seine Termine kommen und wo du den Plan änderst, den es zeigt.
sourceRefs:
  - frontend/src/features/production/planning/views/ProductionPlanningView.vue
  - frontend/src/features/production/utils/productionPlanningTasks.ts
  - backend/src/modules/fulfillment/application/use_cases/production_schedule/recompute_machine_schedule.py
lastVerified: 2026-11-26
---

Der Reiter **Planung** unter Produktion zeichnet jeden eingeplanten, laufenden und pausierten Fertigungsauftrag als Balken auf einer Zeitachse, gruppiert nach Maschine. Er zeigt, wann jeder Auftrag voraussichtlich läuft und worauf er wartet. Das Diagramm liest den Plan nur, Balken lassen sich hier nicht ziehen. Es aktualisiert sich von selbst, wenn sich ein Auftrag, ein Los oder eine Maschine ändert.

## Das Diagramm lesen {#rows}

Jede Maschine ist eine Gruppe, benannt mit den Fertigungsverfahren, die sie abdeckt, und ihre Aufträge folgen in der Reihenfolge der Warteschlange. **Keine Zuweisung** sammelt die Aufträge ohne Maschine, dazu gehören auch Aufträge auf einem Pool, die noch keine Maschine übernommen hat. **Externe Schritte** zeigt die Lieferantenschritte derselben Lose, beschriftet mit Bestellnummer und Lieferant. Ein Lieferantenschritt ohne erwarteten Liefertermin ist als Termin offen markiert und steht an seinem frühestmöglichen Punkt.

Ein Balken trägt die Losnummer, die Teilenummer, die Position und ihr Fertigungsverfahren. Seine Füllung zeigt, wie viel der Menge abgeschlossen ist. Die Pfeile verbinden jeden Schritt eines Loses mit dem Schritt davor, Lieferantenschritte eingeschlossen, damit du nachvollziehen kannst, warum ein Balken dort beginnt. Die senkrechte Linie markiert die aktuelle Zeit.

Die Tabelle links zeigt **Maschine / Auftragsnummer**, **Status**, **Start** und **Dauer (Tage)**, und du kannst nach jeder Spalte sortieren. **Tage**, **Wochen** und **Monate** ändern den Maßstab der Zeitachse.

## Konflikte {#conflicts}

Ein Balken mit orangem Rand hat einen Planungskonflikt, zum Beispiel **Zieltermin überschritten**, **Maschine ausgefallen** oder **Wartet auf Material**. Dieselben Konflikte stehen als Tags auf der Karte des Auftrags in der [Warteschlange](/handbook/production/queue), mit einem Tooltip, der jeden erklärt.

## Woher die Termine kommen {#dates}

Die Termine sind der Fertigungsplan selbst, berechnet aus der Warteschlange jeder Maschine, ihren Arbeitszeiten, den Schritten des Loses und dem Material. Ein neuer Auftrag, den der Plan noch nicht terminiert hat, bekommt bis dahin eine grobe Schätzung. Ein laufender Auftrag, der zu lange läuft, wird bis zu seinem späteren geplanten Ende gezeichnet, der Balken wächst also, solange die Arbeit überzieht. Der Reiter [Kapazität](/handbook/production/capacity) zeigt denselben Plan als gebuchte und freie Stunden je Tag.

## Den Plan ändern {#changes}

Um den Plan zu ändern, ordne Aufträge in der [Warteschlange](/handbook/production/queue) um oder verschieb sie, weise Schritte über [Produktion verwalten](/handbook/production/manage-production) zu, oder lass [Auto-Planen](/handbook/production/auto-plan) die Warteschlangen neu ordnen. Das Diagramm folgt nach wenigen Augenblicken.

## Beispiele {#examples}

Ein Los hat einen Drehschritt und einen Frässchritt. Der Fräsbalken beginnt, wo der Drehbalken endet, und ein Pfeil verbindet die beiden.

Ein Auftrag steht unter **Keine Zuweisung**. Er liegt auf einem Pool und wandert in eine Maschinengruppe, sobald der Bediener ihn auf einer der Maschinen des Pools startet.

Ein Balken hat einen orangen Rand, weil sein Los den Zieltermin verfehlen wird. Rückst du den Auftrag in der Warteschlange seiner Maschine nach vorne, rückt der Balken früher, und der Rand verschwindet, sobald der Auftrag rechtzeitig endet.
