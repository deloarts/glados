---
title: Besprechungsaufgaben
summary: Wie die Aufgaben aus einer Besprechung auf die Aufgabenseite der Zuständigen kommen, wo sie erscheinen und wie du sie abhakst.
sourceRefs:
  - frontend/src/features/todo/views/TodoView.vue
  - frontend/src/features/todo/utils/buildTodoTasks.ts
  - frontend/src/features/todo/composables/useTodoTasks.ts
  - backend/src/modules/fulfillment/application/use_cases/todo/get_todo_sources.py
  - backend/src/modules/workspace/domain/services/meeting_rules.py
lastVerified: 2026-11-10
---

Eine Aufgabe auf einer Karte einer Besprechung landet auf der Aufgabenseite jedes Glados-Benutzers, der für sie zuständig ist, unter der Kategorie **Besprechungen**. Alles andere auf der Aufgabenseite ermittelt Glados selbst, jedes Mal, wenn die Seite öffnet, aus offenen Bestellungen, Bedarfen und Losen: eine Bestellung, die noch abzuschicken ist, eine Lieferung, der du nachgehen musst, ein Los, das zu planen ist. Eine Besprechungsaufgabe ist anders, weil jemand sie aufgeschrieben und dir gegeben hat. Wie Aufgaben entstehen, erklärt [Besprechungskarten](/handbook/workspace/meeting-cards).

## Welche Aufgaben erscheinen

Eine Besprechungsaufgabe steht auf deiner Aufgabenseite, solange sie offen ist, du zu ihren Zuständigen gehörst und die Besprechung gültig ist. Sie braucht keine Berechtigung, denn sie ist deine. Wird eine Besprechung als ungültig markiert, verschwinden ihre offenen Aufgaben von den Aufgabenseiten, bis sie wiederhergestellt wird. Eine Aufgabe, für die nur Kontakte zuständig sind, etwa dass die Kundschaft eine Farbe bestätigt, erreicht gar keine Aufgabenseite. Die Aufgabe nennt ihren Titel, Nummer und Namen der Besprechung und den Bereich ihrer Karte.

## Die vier Spalten

Jede Aufgabe der Aufgabenseite steht nach ihrem Datum in einer Spalte. **Überfällig** hält, was über seinem Datum ist, **Heute**, was heute fällig ist, und **Diese Woche**, was in den nächsten sieben Tagen fällig ist. **Blocker** hält, was kein Datum hat, aber die Arbeit aufhält, und eine Besprechungsaufgabe ohne Datum wartet ebenfalls dort. Eine Aufgabe, die später als nächste Woche fällig ist, erscheint noch nicht.

Standardmäßig zeigt die Seite nur Dringendes: was überfällig ist, heute fällig, mit hoher Priorität oder was die Arbeit aufhält. Eine Besprechungsaufgabe gehört dir, daher erscheint sie immer in der Standardansicht, egal wann sie fällig ist. **Alle anzeigen** mit der Zahl der ausgeblendeten Aufgaben zeigt die anderen.

## Kategorien

Die Ansichtsleiste hat einen Schalter pro Kategorie: **Beschaffung** für Bestellungen und Bedarfe, **Fertigung** für Fertigungsaufträge, **Planung** für Lose und Konflikte im Plan und **Besprechungen** für die Aufgaben aus Besprechungen. Jeder zeigt, wie viele Aufgaben er hält, und **Alle Kategorien** schaltet wieder jede Kategorie ein. Eine Aufgabe der ersten drei Kategorien siehst du nur, wenn du die Berechtigung hast, sie zu erledigen, etwa **Bestellungen schreiben** zum Abschicken einer Bestellung.

## Eine Aufgabe abhaken

Ein Klick auf die Aufgabe öffnet die Besprechung bei der Karte der Aufgabe, wo du sie abhakst. Hakst du sie ab, ist sie für alle erledigt und verschwindet sofort von der Aufgabenseite aller Zuständigen. Wer zuständig ist, hakt die eigene Aufgabe ab, und wer **Besprechungen schreiben** hat, jede. In einer Folgebesprechung steht dieselbe Aufgabe auch unter **Offene Punkte**, und hakst du sie dort ab, ist die ursprüngliche erledigt.

## Beispiele

**Eine Aufgabe aus dem Review von gestern.** Jonas hat dich für „Datenblatt des Sensors schicken“ zuständig gemacht, fällig morgen. Sie steht sofort unter **Diese Woche** in **Besprechungen** und übermorgen unter **Überfällig**.

**Nur die Besprechungsaufgaben.** Du schaltest **Beschaffung**, **Fertigung** und **Planung** aus und lässt **Besprechungen** an. Die Seite zeigt nur, was dir deine Besprechungen gegeben haben.

**In der Besprechung erledigt.** Eine Kollegin hakt deine Aufgabe in der Folgebesprechung ab. Sie verschwindet sofort von deiner Aufgabenseite.
