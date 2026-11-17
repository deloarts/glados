---
title: Besprechungsseite
summary: Was die Seite einer Besprechung zeigt, wie Teilnehmende, Dokumente und der Verlauf funktionieren und was das Markieren als ungültig und eine Folgebesprechung bewirken.
sourceRefs:
  - frontend/src/features/meetings/views/MeetingDetailView.vue
  - frontend/src/features/meetings/components/MeetingControls.vue
  - frontend/src/features/meetings/components/MeetingFormDialog.vue
  - frontend/src/features/meetings/components/MeetingInfoCard.vue
  - frontend/src/features/meetings/components/MeetingDocumentsCard.vue
  - frontend/src/features/meetings/components/MeetingOpenPointsCard.vue
  - backend/src/modules/workspace/application/use_cases/meeting/meetings.py
  - backend/src/modules/workspace/domain/services/meeting_rules.py
  - backend/src/modules/workspace/domain/services/meeting_tags.py
lastVerified: 2026-11-11
---

Die Seite einer Besprechung hält ihr Protokoll. Die Leiste oben zeigt die Nummer, ob die Besprechung gültig ist, ihren Namen, Datum, Uhrzeit und Ort, das Projekt oder Produkt, zu dem sie gehört, **Gesendet** und **Gedruckt**, sobald das Protokoll hinausging, und die Schlagwörter der Besprechung. Links stehen die Karten mit den Notizen, erklärt unter [Besprechungskarten](/handbook/workspace/meeting-cards). Rechts stehen die Karte **Besprechung** mit den Teilnehmenden, die **Dokumente** und die **Verteilung**, die [Besprechungsprotokolle drucken und senden](/handbook/workspace/meeting-distribution) erklärt. **Zurück zu den Besprechungsprotokollen** führt zum Tab zurück.

## Teilnehmende und ihr Status

**Besprechung bearbeiten** öffnet das Formular mit **Name**, **Datum**, **Beginn**, **Ende**, **Ort** und **Schlagwörter**, die unter [Besprechungsprotokolle](/handbook/workspace/meeting-notes) erklärt sind. Unter **Teilnehmende** tippst du einen Namen und wählst einen Glados-Benutzer, einen Kontakt oder, für alle anderen, **„…“ als Gast hinzufügen** mit einer optionalen E-Mail-Adresse. Einen Gast behältst du mit **„…“ als neuen Kontakt speichern**. Alle Teilnehmenden sind **Anwesend**, **Entschuldigt** oder **Verteiler**, das heißt, die Person erhält das Protokoll, ohne teilzunehmen. Für Kontakte brauchst du die Berechtigung **Kontakte lesen**.

Einen Gast, der vergessen werden möchte, entfernst du mit **Gast anonymisieren** auf der Karte **Besprechung**, dafür brauchst du **Besprechungen verwalten**.

## Nächste Besprechung und Folgebesprechung

Unter **Nächste Besprechung** hältst du das vereinbarte Datum, die Uhrzeit und den Ort fest, das ist optional und erscheint auf der Karte **Besprechung** und im PDF. **Folgebesprechung anlegen** legt eine Besprechung desselben Projekts oder Produkts an und übernimmt Name, Ort, Schlagwörter und Teilnehmende. Sie findet zum Datum, zur Uhrzeit und am Ort der nächsten Besprechung statt. Ohne Uhrzeit behält sie die Beginnzeit dieser Besprechung, ohne Datum liegt sie eine Woche später.

Die Folgebesprechung zeigt eine Karte **Offene Punkte** mit den offenen Aufgaben der Besprechung, auf die sie folgt, und der Besprechungen davor. Jede verweist auf ihre Karte, und hakst du eine dort ab, ist auch die ursprüngliche erledigt.

## Dokumente

**Datei hinzufügen** oder Ziehen auf die Karte **Dokumente** lädt Bilder bis 10 MB und PDFs bis 50 MB hoch. Ein Bild, das du in eine Karte einfügst, landet auch hier, markiert als **Bild in einer Karte**. Der Stift neben einer Datei benennt sie um, und der Name behält seine Endung. Löschst du eine Datei, wird sie aus der Besprechung und aus dem Speicher entfernt, und entfernst du ein Bild aus dem Text einer Karte, bleibt die Datei hier.

## Verlauf

**Verlauf** listet alles, was passiert ist: Besprechung angelegt und bearbeitet, Karten hinzugefügt, geändert und gelöscht, Aufgaben hinzugefügt, erledigt und wieder geöffnet, Dateien hinzugefügt und gelöscht, jeder Druck, Download und Versand sowie das Markieren als ungültig und das Wiederherstellen. Ein Druck oder Versand verweist auf seinen Stand. Jede Karte hat außerdem ihre eigenen Versionen, siehe [Besprechungskarten](/handbook/workspace/meeting-cards#history).

## Ungültig und wiederhergestellt

**Als ungültig markieren** fragt nach einem **Grund**. Die Notizen werden schreibgeschützt, die Seite zeigt, wer sie markiert hat und warum, und die offenen Aufgaben verschwinden von allen Aufgabenseiten. **Wiederherstellen** macht die Besprechung wieder gültig und bearbeitbar, mit einer optionalen Notiz. Für beides brauchst du die Berechtigung **Besprechungen verwalten**. Bearbeiten, Karten und Dateien hinzufügen und **Folgebesprechung anlegen** brauchen **Besprechungen schreiben**. Eine Schaltfläche, für die dir die Berechtigung fehlt, bleibt sichtbar, aber deaktiviert, und ihr Tooltip nennt die Berechtigung.

## Beispiele

**Ein Kundenkontakt, der das Protokoll nur liest.** Du fügst den Einkäufer der Kundschaft als **Verteiler** hinzu. Das PDF nennt ihn unter Verteiler, und der Versand schlägt seine Adresse vor.

**Das nächste Review.** Du hältst die nächste Besprechung für Donnerstag um 10:00 in Halle 2 fest. Später legt **Folgebesprechung anlegen** sie für Donnerstag um 10:00 in Halle 2 mit denselben Teilnehmenden an, und ihre Karte **Offene Punkte** listet die noch offenen Aufgaben.

**Das falsche Projekt.** Eine Besprechung wurde bei 26-0142 statt bei 26-0143 erfasst. Du markierst sie mit dem Grund „Beim falschen Projekt erfasst“ als ungültig, und ihre Aufgaben verschwinden von den Aufgabenseiten.
