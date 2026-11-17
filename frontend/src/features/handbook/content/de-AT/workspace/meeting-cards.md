---
title: Besprechungskarten
summary: Wie du das Protokoll einer Besprechung als Karten mit Bereich, Text, Erwähnungen, Beschlüssen und Aufgaben schreibst und wie mehrere Leute gleichzeitig schreiben.
sourceRefs:
  - frontend/src/features/meetings/components/MeetingCard.vue
  - frontend/src/features/meetings/components/MeetingCardEditor.vue
  - frontend/src/features/meetings/components/MeetingScopePopover.vue
  - frontend/src/features/meetings/components/MeetingCardTodos.vue
  - frontend/src/features/meetings/components/MeetingCardDecisions.vue
  - frontend/src/features/meetings/components/MeetingMergeDialog.vue
  - frontend/src/features/meetings/components/MeetingCardHistoryDialog.vue
  - backend/src/modules/workspace/application/use_cases/meeting/cards.py
  - backend/src/modules/workspace/application/use_cases/meeting/todos.py
  - backend/src/modules/workspace/domain/services/meeting_markdown.py
lastVerified: 2026-11-10
---

Das Protokoll einer Besprechung besteht aus Karten, eine pro Thema. **Karte hinzufügen** fügt eine hinzu, und ein Klick auf eine Karte öffnet sie zum Bearbeiten. Jede Karte speichert für sich mit **Karte speichern**, so können mehrere Leute gleichzeitig an verschiedenen Karten derselben Besprechung schreiben.

## Bereich und Symbol

Der Bereich sagt, worum es auf einer Karte geht, etwa Vakuumgreifer oder Liefertermin. Klick oben auf der Karte auf **Bereich festlegen** und tippe ihn ein. Das Feld schlägt die Bereiche vor, die in diesem Projekt oder Produkt schon verwendet werden, die häufigsten zuerst, und bietet **Verwenden** an, wenn sich deiner nur in der Schreibweise von einem bestehenden unterscheidet. **Symbol, optional** fügt eines von zwölf Symbolen hinzu, etwa Mechanik, Software oder Risiko. Der Bereich ist reiner Text und verweist auf nichts anderes in Glados.

## Den Text schreiben

Der Editor hat zwei Modi über demselben Text. **Visuell** zeigt die Formatierung beim Schreiben, und die Werkzeugleiste setzt fett, kursiv, Überschriften, Listen, Inline-Code und Links. **Markdown** zeigt den Text mit seinen Zeichen, und nur Überschriften, fett, kursiv, Listen mit zwei Ebenen, Links, Inline-Code, Erwähnungen und Bilder bleiben erhalten, jede andere Syntax wird zu reinem Text. Mit **@** erwähnst du einen Glados-Benutzer. Eine erwähnte Kollegin wird pro Karte einmal benachrichtigt, siehe [Benachrichtigungen und Berechtigungen](/handbook/account/notifications#kinds).

**Intern, nicht im Druck und nicht in der Mail** markiert eine Karte nur für dein eigenes Team. Sie trägt ein Schloss und bleibt aus jedem PDF draußen, außer der Druck oder Versand nimmt interne Karten auf.

## Beschlüsse und Aufgaben

**Beschluss hinzufügen** hält fest, was die Besprechung beschlossen hat. Das PDF druckt die Beschlüsse bei ihrer Karte und wiederholt sie in einem Überblick.

**Aufgabe hinzufügen** hält eine Aufgabe fest, mit **Zuständig**, einem optionalen Datum unter **Fällig** und einer optionalen **Notiz**. Zuständig sind Glados-Benutzer oder Kontakte der Besprechung. Wer für eine offene Aufgabe zuständig ist, findet sie auf der eigenen Aufgabenseite unter Besprechungen, siehe [Besprechungsaufgaben](/handbook/workspace/meeting-todos). Eine Aufgabe, für die nur Kontakte zuständig sind, etwa dass die Kundschaft eine Farbe bestätigt, trägt **Auf keiner Aufgabenseite** und benachrichtigt niemanden. Hakst du eine Aufgabe ab, ist sie für alle erledigt. Wer **Besprechungen schreiben** hat, hakt jede Aufgabe ab, und wer zuständig ist, die eigene.

## Gleichzeitig schreiben

Während du eine Karte bearbeitest, sehen die anderen darauf „Jonas bearbeitet gerade“. Hat jemand die Karte gespeichert, während du geschrieben hast, öffnet dein Speichern **Änderungen zusammenführen** mit deren Text, deinem Text und den Änderungen dazwischen. Du führst beides im **Zusammengeführten Text** zusammen und speicherst ihn.

Glados behält deinen ungespeicherten Text im Browser. Nach einem Neuladen oder einer verlorenen Verbindung bietet die Karte **Entwurf wiederherstellen** an, oder **Entwurf zusammenführen**, wenn jemand die Karte seither gespeichert hat, und **Verwerfen** wirft den Entwurf weg.

## Kartenverlauf {#history}

**Kartenverlauf** listet die Versionen einer Karte mit den Änderungen von einer zur nächsten. Speichert dieselbe Person innerhalb von 10 Minuten mehrmals, zählt das als eine Version. **Diese Version wiederherstellen** macht einen alten Text wieder zum aktuellen, als neue Version.

Zum Schreiben brauchst du die Berechtigung **Besprechungen schreiben**. Ohne sie bleiben die Schaltflächen sichtbar, aber deaktiviert.

## Beispiele

**Zwei Leute in einer Besprechung.** Anna schreibt die Karte Mechanik, während Jonas Software schreibt. Beide speichern, ohne aufeinander zu warten.

**Eine Aufgabe für die Kundschaft.** Auf der Karte Lackierung fügst du die Aufgabe „Farbe bestätigen“ hinzu, zuständig ist der Kontakt der Kundschaft. Sie steht im PDF und bei den offenen Punkten der Folgebesprechung, aber auf keiner Aufgabenseite.

**Ein Zusammenstoß.** Du und Anna habt beide die Karte Termine geändert. Dein Speichern öffnet **Änderungen zusammenführen**, du behältst ihr neues Datum und deine Notiz und speicherst den zusammengeführten Text.
