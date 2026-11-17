---
title: Besprechungsprotokolle drucken und senden
summary: Wie aus einem Besprechungsprotokoll ein PDF wird, wie du es an die Kundschaft sendest, was die Ausgabe auf dem PDF bedeutet und wie du siehst, was hinausging und was sich seither geändert hat.
sourceRefs:
  - frontend/src/features/meetings/components/MeetingPrintDialog.vue
  - frontend/src/features/meetings/components/MeetingSendDialog.vue
  - frontend/src/features/meetings/components/MeetingSnapshotDialog.vue
  - frontend/src/features/meetings/components/MeetingSentChangesNotice.vue
  - backend/src/modules/workspace/application/use_cases/meeting/distribution.py
  - backend/src/modules/workspace/domain/services/meeting_issue.py
  - backend/src/modules/platform/domain/services/mail_attachment_policy.py
lastVerified: 2026-11-10
---

Das Protokoll einer Besprechung geht als PDF hinaus: gedruckt, heruntergeladen oder per Mail gesendet. **Drucken** und **Senden** auf der Besprechungsseite öffnen ihre Dialoge. Jeder Druck, Download und Versand steht auf der Karte **Verteilung**, und Glados hält fest, was genau jedes PDF enthielt.

## Was das PDF enthält

Das PDF zeigt die Eckdaten der Besprechung, die Teilnehmenden nach anwesend, entschuldigt und Verteiler, die Karten mit Bereich und Verfasser, die Beschlüsse mit einem Überblick, die Aufgaben und die Liste der Dokumente. **Aufgaben aufnehmen** und **Dokumente auflisten** sind standardmäßig an. Interne Karten bleiben draußen, außer du hakst für dieses eine PDF **Interne Karten aufnehmen** an, so kann dasselbe Protokoll an die Kundschaft gehen. Die **Sprache** des PDFs wählst du im Dialog.

## Ausgabe und Entwurf

Das PDF trägt eine Ausgabe. Jeder Versand ist die nächste Ausgabe, etwa Ausgabe 2 · 6. Nov. 2026. Ein Druck oder Download trägt die letzte Ausgabe, solange sich seit ihrem Versand nichts geändert hat, sonst steht Entwurf nach Ausgabe 2 darauf, und vor dem ersten Versand nur Entwurf.

## Drucken und herunterladen

**PDF herunterladen** speichert die Datei. Zum Drucken auf einem Dokumentdrucker brauchst du die Berechtigung **Dokumente drucken**. Hat jemand eine Karte geändert, während der Dialog offen war, lehnt Glados das PDF ab und nennt die Karte, die Seite zeigt das aktuelle Protokoll, und drückst du noch einmal, entsteht das PDF daraus.

## Senden

**Senden** füllt **An** mit Vorschlägen: den Teilnehmenden, die Kontakte oder Gäste mit Adresse sind, und den Kontakten des Projekts und des Produkts, die Besprechungsprotokolle erhalten. Die weiteren Kontakte der Kundschaft und ihre eigene Adresse werden angeboten, aber nicht angehakt. **CC** beginnt mit dir. **Betreff** und **Text** kommen aus der Admin-Vorlage Besprechungsprotokoll in der gewählten Sprache, und der Text endet mit dem Satz, dass das Protokoll als angenommen gilt, wenn niemand innerhalb von 7 Tagen widerspricht. Beides kannst du vor dem Senden ändern.

Das PDF ist immer angehängt. **Dokumente der Besprechung anhängen** fügt die Dateien der Besprechung hinzu, solange die Mail unter der Anhangsgrenze bleibt, die die Administration festgelegt hat, 10 MB, wenn sie nicht geändert wurde, und der Dialog nennt die weggelassenen Dateien. Lehnt der Mailserver die Mail ab, zeigt der Dialog seinen Fehler, und nichts wird vermerkt. Zum Senden brauchst du **Besprechungen schreiben** und **E-Mails versenden**, und eine ungültige Besprechung lässt sich nicht senden.

## Was hinausging und was sich seither geändert hat {#distribution}

Auf der Karte **Verteilung** zeigt **Wie gesendet**, **Wie gedruckt** oder **Wie heruntergeladen** das Protokoll so, wie das PDF es enthielt, mit den Empfängern und den angehängten Dateien. **Änderungen seither** vergleicht diesen Stand mit dem Protokoll heute: hinzugefügte, entfernte und geänderte Karten mit ihren Zeilen, Beschlüsse und neue Aufgaben. Interne Karten, die ein Stand wegließ, bleiben auch beim Vergleich draußen.

Eine Karte, die nach dem letzten Versand geändert wurde, trägt **Nach dem Versand geändert**, eine neue **Nach dem Versand hinzugefügt**. Ein Hinweis über den Karten bietet **Änderungen anzeigen** und **Erneut senden** an. Eine abgehakte Aufgabe zählt nicht als Änderung.

## Beispiele

**Protokoll an die Kundschaft.** Nach dem Review drückst du **Senden**. Unter An stehen die Projektleiterin der Kundschaft und der Einkäufer aus dem Verteiler. Die interne Karte zu den Preisen bleibt draußen, und das PDF sagt Ausgabe 1.

**Eine Korrektur.** Am nächsten Tag korrigiert ein Kollege ein Datum auf einer Karte. Die Karte zeigt **Nach dem Versand geändert**, **Änderungen anzeigen** zeigt die geänderte Zeile, und **Erneut senden** sendet Ausgabe 2.

**Zu viele Zeichnungen.** Die Besprechung hat 14 MB an PDFs. Der Versand hängt das Protokoll und die Dateien an, die unter 10 MB passen, und nennt den Rest, den du auf anderem Weg teilst.
