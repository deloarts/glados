---
title: Artikelgruppen
summary: Wie Artikelgruppen deine Teile gliedern, wie ihre Namen in jeder Sprache gepflegt werden und wie ihre Reihenfolge bestimmt, was die Auswahlfelder zuerst anbieten.
sourceRefs:
  - backend/src/modules/catalogue/domain/services/article_group_rules.py
  - backend/src/modules/catalogue/domain/services/label_name_rules.py
  - backend/src/modules/catalogue/application/services/labeled_entity_crud.py
  - backend/src/modules/catalogue/application/services/catalogue_list_order.py
lastVerified: 2026-11-10
---

Artikelgruppen sind deine eigene Einkaufsgliederung, etwa Pneumatik, Verbindungselemente oder Blechteile. Ein Teil kann zu mehreren gehören, und jede Gruppe erscheint als farbiges Etikett beim Teil. Die Liste findest du unter Ressourcen, **Artikelgruppen**. Einträge werden archiviert, nie gelöscht, also behalten Teile ihre Gruppen.

## Name und Beschreibung in jeder Sprache

**Name** und **Beschreibung** haben ein Eingabefeld je Sprache, die die Anwendung anbietet. Der Name braucht einen Text in der Standardsprache, die als erste kommt, die anderen Sprachen sind optional. Eine Sprache, die du leer lässt, zeigt den Namen der Standardsprache. Ein Name hat bis zu 200 Zeichen, eine Beschreibung bis zu 4000.

Zwei Gruppen, die nicht archiviert sind, dürfen in derselben Sprache nicht denselben Namen zeigen. Groß- und Kleinschreibung und Leerzeichen rund um den Namen zählen nicht, also kollidieren Pneumatik und pneumatik. Ein deutscher Name darf trotzdem dem englischen Namen einer anderen Gruppe gleichen.

## Farben

**Label-Farbe** ist der Hintergrund des Etiketts und **Schriftfarbe** sein Text, **Vorschau** zeigt das Ergebnis. Eine neue Gruppe beginnt mit Grau und Schwarz. Ist die Kombination schwer lesbar, meldet das Formular „Diese Farbkombination ist in Etikettengröße schwer lesbar.“ und bietet **Lesbare Schriftfarbe verwenden** an, das die Schriftfarbe auf Schwarz oder Weiß setzt, je nachdem, was auf dem Etikett besser lesbar ist.

## Berechtigungen und Archivieren

Zum Anlegen, Bearbeiten, Verschieben, Archivieren und Wiederherstellen einer Gruppe brauchst du die Berechtigung **Artikelgruppen schreiben**. Ohne sie sind die Schaltflächen deaktiviert. Das Wiederherstellen wird abgelehnt, wenn inzwischen eine aktive Gruppe ihren Namen in irgendeiner Sprache verwendet. Archivierte Gruppen bleiben bei ihren Teilen, und die Auswahlfelder zeigen sie zuletzt mit dem Etikett **Archiviert**.

## Die Reihenfolge der Liste

In der Reihenfolge der Tabelle bieten die Auswahlfelder die Gruppen an, also stell die meistverwendeten nach oben. Darfst du Artikelgruppen bearbeiten, zeigt die erste Spalte in jeder Zeile einen Griff. Halt den Griff fest und zieh die Zeile an ihren neuen Platz; eine Linie zeigt, wo sie landet. Der Griff erscheint nur, solange keine Sortierung, Suche und kein Filter aktiv ist, weil die Zeilen dann in einer anderen Reihenfolge stehen. Das Anzeigen archivierter Gruppen blendet ihn nicht aus. Eine neue Gruppe kommt ans Ende der Liste.

## Wo Artikelgruppen verwendet werden

Du setzt Artikelgruppen bei Zukaufteilen und Fertigungsteilen, und bei einem Lieferanten hältst du damit fest, was er liefert. **Standard-Artikelgruppen** in den Einstellungen zum EPLAN Data Portal bekommt jedes Teil, das aus dem Portal angelegt wird. Das SolidWorks-Add-in bekommt jeden Namen in der Sprache, die unter **Sprache des Add-ins** in den Einstellungen zu SolidWorks PDM gewählt ist.

## Beispiele

**Eine neue Gruppe.** Du legst eine Gruppe mit Pneumatik für Deutsch und Pneumatics für Englisch an, mit blauem Etikett und weißer Schrift. Wer Deutsch eingestellt hat, sieht Pneumatik bei seinen Teilen, wer Englisch eingestellt hat, Pneumatics.

**Ein doppelter Name.** Eine Kollegin nennt eine neue Gruppe auf Deutsch pneumatik. Das Speichern wird abgelehnt, weil eine aktive Gruppe diesen Namen auf Deutsch schon zeigt, egal in welcher Schreibweise.

**Eine Gruppe nach oben schieben.** Die Tabelle ist nach Name sortiert, darum ist kein Griff zu sehen. Du klickst auf **Sortieren nach**, um die Sortierung aufzuheben, hältst den Griff von Pneumatik fest und ziehst sie ganz nach oben. Ab jetzt bieten die Teileformulare sie zuerst an.
