---
title: Infoscreens
summary: Wie du einen Bildschirm für die Wandbildschirme anlegst, welche Sprache er spricht und wie du ihn in der Vorschau ansiehst und archivierst.
sourceRefs:
  - backend/src/modules/operations/domain/services/infoscreen_rules.py
  - backend/src/read/application/use_cases/infoscreen/build_infoscreen_feed.py
  - backend/src/modules/operations/domain/value_objects/infoscreen.py
  - backend/src/modules/operations/application/use_cases/infoscreen/get_infoscreen_feed.py
lastVerified: 2026-11-10
---

Ein Infoscreen ist das, was ein Wandbildschirm zeigt: eine Reihe von Seiten, durch die der Fernseher von selbst blättert. Du baust Infoscreens unter Ressourcen, **Infoscreens** und weist einen davon im Tab **Terminals** einem Bildschirm zu. Ein Infoscreen kann auf vielen Bildschirmen laufen, die Spalte **Angezeigt auf** listet sie. Ansehen und die Vorschau öffnen darf jede und jeder. Zum Anlegen, Bearbeiten und Archivieren brauchst du **Infoscreens bearbeiten**, ohne die Berechtigung sind die Schaltflächen deaktiviert und zeigen einen Hinweis. Seiten, Leisten und Widgets eines Infoscreens erklärt [Infoscreen-Seiten und Widgets](/handbook/resources/infoscreen-pages).

## Das Aussehen eines Infoscreens

Klick auf **Neuer Infoscreen** und gib ihm einen **Name**. Die **Beschreibung** ist optional. Der **Farbmodus** ist Dunkel, außer du wählst Hell, das passt zu hellen Büros. **Theme** und **Primärfarbe** sind optional; ohne sie nimmt der Infoscreen den Standard dieser Installation. **Seitenzeit (Sekunden)** legt fest, wie lange jede Seite stehen bleibt, zwischen 10 und 600 Sekunden. **Banner dieser Installation anzeigen** blendet das Banner ein, das alle sehen, für Ankündigungen, die alle betreffen. **Anzeigezeiten** legt fest, wann sich die Bildschirme mit diesem Infoscreen ausschalten, wie [Anzeigezeiten](/handbook/resources/display-schedule) erklärt. **Anzeigezeitplan** im Menü der Zeile stellt dieselben Zeiten ein, ohne den Editor zu öffnen, und die Spalte **Zeitplan** fasst sie zusammen.

## Sprache {#language}

Die **Sprache** ist optional und bestimmt die Wörter, die der Bildschirm selbst schreibt, etwa Datum, Wochentage, die voreingestellten Titel der Widgets und die Beschriftungen in den Leisten. Mit **Standard dieser Installation** folgt der Infoscreen der Standardsprache aus den allgemeinen Einstellungen, und die Spalte **Sprache** zeigt, welche das gerade ist, zum Beispiel Standard dieser Installation (Deutsch). Texte, die du eingibst, wie Titel, der eigene Text und Nachrichten, bleiben, wie du sie getippt hast. Die Vorschau zeigt den Infoscreen in seiner Sprache.

## Keine Namen am Bildschirm

Ein Infoscreen zeigt nie die Namen von Personen, etwa von Bedienern oder von der Person, die etwas bestellt hat. Kundennamen bleiben verborgen, außer du hakst **Kundennamen anzeigen** bei den Widgets Fällige Lose oder Verspätete Lose an, denn auch Firmennamen können in einem Besucherbereich vertraulich sein.

## Vorschau und Archiv

Mit der rechten Maustaste auf eine Zeile findest du **Bearbeiten**, **Vorschau**, **Anzeigezeitplan** und **Archivieren** oder **Wiederherstellen**. Dieselben Aktionen erscheinen als Knöpfe in jeder Zeile, sobald du unter **Ansichten** **Aktionen anzeigen** einschaltest. **Vorschau** öffnet die zuletzt gespeicherte Fassung in einem neuen Tab, genau so, wie ein Fernseher sie zeigt; speichere also zuerst, um deine Änderungen zu sehen. **Archivieren** nimmt einen Infoscreen aus der Liste und aus der Auswahl im Tab Terminals, darum gib den Bildschirmen, die ihn zeigen, vorher einen anderen. **Archivierte anzeigen** listet archivierte Infoscreens wieder, und **Wiederherstellen** holt einen zurück.

## Beispiele

**Ein Infoscreen fürs Büro.** Du legst Bürotafel an, wählst Hell und eine **Seitenzeit (Sekunden)** von 60 und fügst die Widgets Fällige Lose und Erwartete Lieferungen hinzu. Im Tab Terminals weist du sie dem Bildschirm im Büro zu.

**Ein Infoscreen auf Englisch.** Die Installation spricht Deutsch, aber das Team in der Halle liest Englisch. Du stellst die **Sprache** auf English, und Datum und Überschriften auf dem Bildschirm werden englisch, während deine Nachricht bleibt, wie du sie getippt hast.
