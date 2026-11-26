---
title: Kapazität
summary: Wie der Tab Kapazität den Produktionszeitplan als verplante und verfügbare Stunden je Tag zeigt, eine Zeile je Maschine und eine je Pool, und was eine rote, leere oder ungelöste Zelle bedeutet.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_schedule/get_schedule_board.py
  - backend/src/modules/fulfillment/domain/services/scheduling/capacity.py
  - backend/src/modules/fulfillment/domain/services/scheduling/machine_calendar.py
  - backend/src/modules/fulfillment/domain/services/scheduling/forward_walk.py
  - frontend/src/features/production/utils/capacityUtilization.ts
lastVerified: 2026-11-26
---

Der Tab Kapazität zeigt denselben Produktionszeitplan wie die Warteschlange, nur anders gelesen. Statt einer Karte je Auftrag zeigt er verplante und verfügbare Stunden je Tag, damit du auf einen Blick siehst, welche Maschinen und Pools noch Luft haben und welche knapp sind. Die Tage wählst du mit **Zeitraum**, und [Auto-Planen](/handbook/production/auto-plan) startest du mit dem Button **Auto-Planen** in derselben Leiste.

## Die zwei Tabellen {#grids}

**Maschinen** steht zuerst, mit einer Zeile je Maschine. Die Zeile **Keine Zuweisung** darunter sammelt die Aufträge ohne Maschine: manuelle Schritte, Aufträge ohne Maschine und ohne Pool, und Aufträge eines Pools ohne Mitglieder. **Maschinenpools** folgt, mit einer Zeile je Pool. Eine Poolzeile zählt nur zusammen, was seine Maschinen für ihn tragen, denn ein Pool ist nie eine eigene Ressource.

Klick auf die Zahl in der Spalte **Aufträge** einer Zeile, um jeden Auftrag zu sehen, den diese Zeile über den ganzen Zeitraum zählt. Der Dialog zeigt **Auftrag**, **Los**, **Projekt**, **Artikel**, **Schritt**, **Zeitfenster** und **Konflikte**.

## Verplant, verfügbar, überbucht {#minutes}

Jede Tageszelle zeigt die verplanten gegenüber den verfügbaren Stunden. Die verfügbaren Stunden kommen aus dem Arbeitskalender der Maschine: ihrer eigenen oder der Standard-Arbeitswoche, ihren Datumsausnahmen, Feiertagen und Betriebsurlauben und ihren Ausfallzeiten. Eine Nachtschicht zählt für den Tag, an dem sie beginnt. Eine Zelle ist ab 70 Prozent der verfügbaren Zeit orange und über 100 Prozent rot, und ein Hover über eine rote Zelle zeigt, wie weit sie drüber ist. Vergangene Tage und Tage ohne Arbeitszeit sind ausgegraut, und heute ist hervorgehoben.

Die Zeile einer Maschine zählt jeden Auftrag auf dieser Maschine und dazu jeden Poolauftrag, den der Zeitplan gerade auf ihr platziert. Eine Poolzeile ist die Summe dessen, was seine Mitglieder für ihn tragen, ist eine Poolzeile rot, ist also mindestens ein Mitglied auch rot.

## Ungelöste Aufträge {#unresolved}

Ein Poolauftrag, der noch keine Maschine hat, zeigt im Auftragsdialog neben seinem Zeitfenster ein Tag **Ungelöst**. Seine Termine sind echt, aber die Maschine, auf der er gezählt wird, ist nur eine Prognose. Ein Hover über das Tag nennt diese Maschine, wenn es eine gibt. Fix wird die Maschine beim Start des Auftrags oder auf einem der anderen Wege, die [Produktion verwalten](/handbook/production/manage-production#resolve) beschreibt.

## Wenn die Übersicht nachzieht {#stale}

Nach einer Änderung, die Plantermine verschiebt, arbeitet Glados die neuen Termine im Hintergrund in jeden Auftrag ein. Bis das fertig ist, sagt ein Hinweis, dass Änderungen seit einer bestimmten Uhrzeit noch in die gespeicherten Plantermine eingearbeitet werden. Die Übersicht selbst ist schon aktuell. Der Hinweis verschwindet, sobald alle gespeicherten Termine nachgezogen sind.

## Warum ist ein Platz frei? {#free-slots}

Ein freier Tag heißt nicht, wer zuerst kommt, mahlt zuerst. Die Warteschlange jeder Maschine wird in ihrer festen Reihenfolge geplant, und jeder Auftrag startet zum frühesten Zeitpunkt, den seine eigene Reihe erlaubt, ein späterer Auftrag springt also nie in eine Lücke, die ein früherer gelassen hat. Eine Lücke bleibt auch leer, wenn der nächste Auftrag auf seinen vorherigen Schritt, auf eine Lieferung plus die Reaktionszeit oder auf sein Rohmaterial wartet, oder wenn ein Auftrag im fixierten Zeitraum seinen Platz behält. Die Regeln stehen unter [Wann ein Auftrag starten kann](/handbook/production/auto-plan-timing).

Ein Beispiel: Eine Drehmaschine zeigt den Mittwoch frei, obwohl ein Auftrag auf ihr wartet. Sein vorheriger Schritt, ein Härteschritt bei einem Lieferanten, wird am Mittwoch zurückerwartet, und mit einem Tag Reaktionszeit kann der Drehauftrag nicht vor Donnerstag starten.
