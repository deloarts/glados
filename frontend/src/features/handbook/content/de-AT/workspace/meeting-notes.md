---
title: Besprechungsprotokolle
summary: Wie der Tab Besprechungsprotokolle eines Projekts oder Produkts seine Besprechungen listet, wie du eine neue beginnst und wie du Bereiche umbenennst.
sourceRefs:
  - frontend/src/features/meetings/components/MeetingNotesTable.vue
  - frontend/src/features/meetings/components/MeetingNotesViews.vue
  - frontend/src/features/meetings/components/MeetingNotesControls.vue
  - frontend/src/features/meetings/components/MeetingScopeRenameDialog.vue
  - backend/src/modules/workspace/application/use_cases/meeting/meetings.py
  - frontend/src/features/meetings/components/MeetingTagInput.vue
  - backend/src/modules/workspace/application/use_cases/meeting/scopes.py
  - backend/src/modules/workspace/application/use_cases/meeting/tags.py
lastVerified: 2026-11-11
---

Der Tab **Besprechungsprotokolle** eines Projekts oder Produkts listet die Besprechungen dazu, etwa ein Design-Review oder einen Baustellentermin mit der Kundschaft. Jede Besprechung gehört zu genau einem Projekt oder einem Produkt und hat eine Nummer wie MTG-26-0021, im Format, das ein Admin unter **Einstellungen**, **Nummerierung** festlegt. Alle, die bei Glados angemeldet sind, können jede Besprechung lesen. Ein Klick auf eine Zeile öffnet die Seite der Besprechung, auf der du das Protokoll schreibst, druckst und sendest, siehe [Besprechungsseite](/handbook/workspace/meeting).

## Was die Tabelle zeigt

Jede Zeile zeigt den Status, Datum und Uhrzeit, die Bereiche der Karten, den Namen mit der Nummer darunter, die Schlagwörter der Besprechung, den Anfang der Notizen, die offenen Aufgaben, die Teilnehmenden und den Ort. **Status** sagt **Gültig** oder **Ungültig**, und kleine Symbole zeigen, ob das Protokoll gesendet oder gedruckt wurde. **Bereich** zeigt das Thema jeder Karte als Chip, und der Chip einer internen Karte ist als solcher markiert. **Offene Aufgaben** zählt die Aufgaben, die noch niemand abgehakt hat, und nennt die überfälligen in Rot. Im Feld über **Schlagwörter** wählst du eines der verwendeten Schlagwörter, und die Tabelle listet dann nur die Besprechungen, die es tragen, egal in welcher Schreibweise. **Zurücksetzen** in der Ansichtsleiste entfernt den Filter wieder.

## Eine Besprechung beginnen

**Neue Besprechung** öffnet das Formular. **Name**, **Datum**, **Beginn** und **Ende** sind Pflicht, und das Ende darf nicht vor dem Beginn liegen. **Ort** ist optionaler freier Text, etwa ein Raum oder ein Teams-Termin. Auch **Schlagwörter** sind optional, etwa Meilenstein oder Abnahme, damit du die Besprechung leicht wiederfindest. Beim Tippen bietet das Feld die Schlagwörter anderer Besprechungen an, und Enter oder ein Komma fügt das Getippte als neues hinzu. Eine Besprechung trägt bis zu 10 Schlagwörter mit höchstens 40 Zeichen, und ein Schlagwort, das ein anderes nur in anderer Groß- und Kleinschreibung wiederholt, bleibt einmal stehen. Unter **Teilnehmende** fügst du Glados-Benutzer, Kontakte und Gäste hinzu, jeweils mit ihrem Status. Unter **Nächste Besprechung** kannst du festhalten, wann und wo die nächste stattfindet, das ist optional. **Besprechung anlegen** speichert sie und öffnet ihre Seite, bereit für die erste Karte.

Zum Anlegen brauchst du die Berechtigung **Besprechungen schreiben**. Ohne sie bleibt die Schaltfläche sichtbar, aber deaktiviert, und ihr Tooltip nennt die Berechtigung.

## Ansichten bei einem Produkt

Bei einem Produkt listet der Tab die eigenen Besprechungen des Produkts und auch die aller seiner Projekte, bis du **Projekte ausblenden** drückst, mit einer Spalte **Projekt**. **Nach Projekt gruppieren** gruppiert die Zeilen nach Projekt. Beides sitzt in der Ansichtsleiste neben **Synchronisieren**, **Sortieren nach**, **Ungültige anzeigen** und **Zurücksetzen**, das jede Ansicht auf ihren Standard zurückstellt. Ungültige Besprechungen bleiben ausgeblendet, bis du **Ungültige anzeigen** einschaltest.

Jede Spalte hat einen Filter in der Zeile unter ihrer Überschrift: den Status, etwa **Nicht gesendet**, einen Tag oder einen Zeitraum, die Projekte, eine Suche in den Bereichen, im Namen samt Nummer, in den Notizen und im Ort, ob die Besprechung offene oder überfällige Aufgaben hat, die Teilnehmenden und das Schlagwort. Die Filter grenzen die Liste sofort ein, und **Zurücksetzen** entfernt sie alle.

## Einen Bereich umbenennen

Der Bereich einer Karte ist freier Text, darum kann dasselbe Thema in zwei Schreibweisen landen. **Bereich umbenennen** wählt einen hier verwendeten Bereich, zeigt, auf wie vielen Karten er steht, und benennt ihn auf allen Karten der gültigen Besprechungen dieses Projekts um, bei einem Produkt auch bei denen seiner Projekte. Dafür brauchst du **Besprechungen schreiben**.

## Eine Besprechung löschen

Ein Rechtsklick auf eine Zeile, oder **Aktionen anzeigen**, bietet **Öffnen**, **In neuem Tab öffnen** und **Besprechung löschen**. Das Löschen entfernt die Besprechung mit ihren Notizen, Aufgaben und Dokumenten aus allen Listen. Dafür brauchst du die Berechtigung **Besprechungen verwalten**, ohne sie ist der Eintrag deaktiviert. Eine Besprechung, die beim falschen Projekt erfasst wurde, markierst du besser auf ihrer Seite als ungültig, so bleibt sie nachvollziehbar.

## Beispiele

**Ein Design-Review.** Im Projekt 26-0142 drückst du **Neue Besprechung**, gibst Design-Review Greifer ein, heute von 10:00 bis 11:30, Raum Donau, und fügst zwei Kollegen und die Projektleiterin der Kundschaft hinzu. Die Besprechung öffnet sich als MTG-26-0021, bereit für ihre Karten.

**Alle Besprechungen einer Maschine.** Beim Produkt lässt du **Projekte ausblenden** aus und schaltest **Nach Projekt gruppieren** ein. Die eigenen Besprechungen des Produkts und die jedes seiner Projekte erscheinen in Gruppen.

**Die Meilensteine finden.** Die Besprechungen, die eine Projektphase abschließen, versiehst du mit dem Schlagwort Meilenstein. Später wählst du Meilenstein im Feld über **Schlagwörter**, und die Tabelle zeigt nur diese Besprechungen.

**Ein Thema, zwei Schreibweisen.** Manche Karten sagen Vakuumgreifer, andere Vakuum-Greifer. **Bereich umbenennen** benennt den ersten in den zweiten um, und alle Karten zeigen denselben Chip.
