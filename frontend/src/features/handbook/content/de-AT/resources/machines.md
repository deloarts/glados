---
title: Fertigungsmaschinen
summary: Wie du eine Fertigungsmaschine, ihre Arbeitszeiten, Kalenderausnahmen und Stillstände einrichtest und wie sie sich jeweils auf die Planung auswirken.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_machine/create_machine.py
  - backend/src/modules/fulfillment/application/use_cases/production_machine/archive_machine.py
  - backend/src/modules/fulfillment/application/use_cases/production_machine/working_hours.py
  - backend/src/modules/fulfillment/application/use_cases/production_machine/calendar_exceptions.py
  - backend/src/modules/fulfillment/application/use_cases/production_machine/downtimes.py
  - backend/src/modules/fulfillment/application/use_cases/production_machine/move_machine.py
  - backend/src/modules/fulfillment/domain/services/production_machine_rules.py
  - backend/src/modules/fulfillment/domain/services/production_machine_status_rules.py
  - backend/src/modules/fulfillment/domain/services/machine_downtime_rules.py
lastVerified: 2026-11-10
---

Die Liste **Fertigungsmaschinen** enthält jede Maschine, auf der die Planung Arbeit einplanen kann. Eine Maschine sagt, welche Fertigungsmethoden sie kann, wann sie arbeitet und wann sie steht, und die Planung legt einen Auftrag nur auf eine Maschine, die alle seine Schritte kann und Arbeitszeit hat.

## Eine Maschine einrichten

**Interner Name**, **Hersteller** und **Modell** sind Pflicht. **Fähigkeiten** listet die Fertigungsmethoden, die die Maschine kann. **Max. Bauteilgröße** ist optionaler freier Text, etwa 3000 x 1500 mm, und **Notiz** nimmt alles andere. Hak **QS- / Messmaschine** bei einer Messmaschine an: Sie übernimmt nur Prüfarbeit, nie Fertigung, deshalb werden ihre Fähigkeiten geleert und das Feld gesperrt.

## Status

Die Spalte **Status** setzt Glados selbst. Eine Maschine zeigt Steht, solange ein Stillstand offen ist. Sonst zeigt sie Läuft, wenn einer ihrer Aufträge in Arbeit ist, Pausiert, wenn einer pausiert ist, und andernfalls Leerlauf.

## Arbeitszeiten und Ausnahmen {#working-hours}

**Standardkalender** in der Werkzeugleiste legt die Wochenstunden fest, die jede Maschine ohne eigene Zeiten verwendet, und auch Handarbeit wird darin geplant. Zum Speichern brauchst du die Berechtigung **Fertigungsmaschinen schreiben**.

**Kalender verwalten** in einer Zeile öffnet den Kalender einer Maschine. Unter **Arbeitszeiten** folgt **Globalen Standard verwenden** dem Standardkalender, während **Eigene Überschreibung** der Maschine eigene Wochenschichten gibt. **Kalenderausnahmen** ändern ein einzelnes Datum, höchstens eine pro Datum: Hak **Geschlossen** für einen freien Tag an, oder setz einen **Beginn** und die verfügbaren Minuten, 0 bis 1440, für ein Wartungsfenster oder eine Zusatzschicht. Eine Ausnahme öffnet eine Maschine auch an einem Feiertag.

## Stillstände {#downtimes}

Ein Stillstand hält fest, dass eine Maschine nicht arbeiten kann. **Beginn** ist Pflicht, ein leeres **Ende** heißt, dass er noch läuft, und **Grund** ist Defekt, Wartung, Werkzeugwechsel, Kein Bediener, Kein Material oder Sonstiges, dazu eine optionale **Notiz**. Eine Maschine kann nur einen laufenden Stillstand haben, und beendete Stillstände einer Maschine dürfen sich nicht überschneiden. Die Planung lässt die Zeit aus, in der eine Maschine steht, und Auto-Plan überspringt sie. **Stillstände** in der Werkzeugleiste listet sie für alle Maschinen.

## Die Liste verwalten

Zum Anlegen und Bearbeiten von Maschinen, ihren Kalendern und Stillständen, zum Verschieben und zum Archivieren oder Wiederherstellen brauchst du die Berechtigung **Fertigungsmaschinen schreiben**. Ohne sie sind die Schaltflächen deaktiviert. Eine Maschine lässt sich nicht archivieren, solange sie noch eingeplante, laufende oder pausierte Fertigungsaufträge hat. Nach dem Bearbeiten, Archivieren und Wiederherstellen wird der Zeitplan neu berechnet. **Maschine ansehen** öffnet die Seite der Maschine.

Die Reihenfolge der Liste ist auch die Reihenfolge der Plantafel und jeder Maschinenliste. Darfst du Fertigungsmaschinen bearbeiten, zeigt die erste Spalte in jeder Zeile einen Griff. Halt den Griff fest und zieh die Zeile an ihren neuen Platz; eine Linie zeigt, wo sie landet. Der Griff erscheint nur, solange keine Sortierung, Suche, kein Filter und kein **Gruppieren nach** aktiv ist, weil die Zeilen dann in einer anderen Reihenfolge stehen. Neue Maschinen kommen ans Ende.

## Beispiele

**Ein neuer Laser.** Leg den Laser mit Hersteller und Modell an und wähl Laserschneiden unter **Fähigkeiten**. Er arbeitet zu den Standardzeiten, und Auto-Plan kann jetzt Laserschritte auf ihn legen.

**Ein zusätzlicher Samstag.** Füg unter **Kalenderausnahmen** der Drehmaschine den nächsten Samstag mit **Beginn** 06:00 und 480 Minuten hinzu. Die Drehmaschine arbeitet an dem Tag von 06:00 bis 14:00, obwohl ihre Wochenstunden den Samstag frei lassen.

**Ein Defekt.** Leg einen Stillstand mit **Grund** Defekt an und lass **Ende** leer. Die Maschine zeigt Steht, und Auto-Plan plant um sie herum. Läuft sie wieder, beende den Stillstand.
