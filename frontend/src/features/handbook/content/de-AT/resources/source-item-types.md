---
title: Rohblocktypen
summary: Was ein Rohblocktyp ist, wie sein Name in jeder Sprache gepflegt wird und wie die Reihenfolge der Liste bestimmt, was die Typauswahl zuerst anbietet.
sourceRefs:
  - backend/src/modules/catalogue/domain/services/source_item_type_rules.py
  - backend/src/modules/catalogue/domain/services/label_name_rules.py
  - backend/src/modules/catalogue/application/services/labeled_entity_crud.py
  - backend/src/modules/catalogue/application/services/catalogue_list_order.py
lastVerified: 2026-11-10
---

Ein Rohblocktyp ist die Art eines Rohmaterialblocks, etwa Rundmaterial, Flachmaterial oder Platte. Jeder Rohblock hat einen, und zusammen mit Abmessung und Material unterscheidet der Typ die Rohblöcke voneinander. Die Liste findest du unter Ressourcen, **Rohblocktypen**. Einträge werden archiviert, nie gelöscht, also behalten Rohblöcke ihren Typ.

## Name und Beschreibung in jeder Sprache

**Name** und **Beschreibung** haben ein Eingabefeld je Sprache, die die Anwendung anbietet. Der Name braucht einen Text in der Standardsprache, die als erste kommt, die anderen Sprachen sind optional. Eine Sprache, die du leer lässt, zeigt den Namen der Standardsprache. Ein Name hat bis zu 200 Zeichen, eine Beschreibung bis zu 4000.

Zwei Typen, die nicht archiviert sind, dürfen in derselben Sprache nicht denselben Namen zeigen. Groß- und Kleinschreibung und Leerzeichen rund um den Namen zählen nicht, also kollidieren Rundmaterial und rundmaterial. Ein deutscher Name darf trotzdem dem englischen Namen eines anderen Typs gleichen.

## Farben

**Label-Farbe** ist der Hintergrund des Etiketts und **Schriftfarbe** sein Text, **Vorschau** zeigt das Ergebnis. Ein neuer Typ beginnt mit Grau und Schwarz.

## Berechtigungen und Archivieren

Zum Anlegen, Bearbeiten, Verschieben, Archivieren und Wiederherstellen eines Typs brauchst du die Berechtigung **Rohblocktypen schreiben**. Ohne sie sind die Schaltflächen deaktiviert. Das Wiederherstellen wird abgelehnt, wenn inzwischen ein aktiver Typ seinen Namen in irgendeiner Sprache verwendet. Archivierte Typen bleiben bei ihren Rohblöcken, und die Typauswahl zeigt sie zuletzt mit dem Etikett **Archiviert**.

## Die Reihenfolge der Liste

In der Reihenfolge der Tabelle bietet die Typauswahl die Typen an, also stell die meistverwendeten nach oben. Darfst du Rohblocktypen bearbeiten, zeigt die erste Spalte in jeder Zeile einen Griff. Halt den Griff fest und zieh die Zeile an ihren neuen Platz; eine Linie zeigt, wo sie landet. Der Griff erscheint nur, solange keine Sortierung, Suche und kein Filter aktiv ist, weil die Zeilen dann in einer anderen Reihenfolge stehen. Das Anzeigen archivierter Typen blendet ihn nicht aus. Ein neuer Typ kommt ans Ende der Liste.

## Wo Rohblocktypen verwendet werden

Du wählst den Typ unter **Typ**, wenn du einen Rohblock anlegst oder bearbeitest, und die Rohblocktabelle und die Details eines Rohblocks zeigen ihn an. Das SolidWorks-Add-in bekommt jeden Namen in der Sprache, die unter **Sprache des Add-ins** in den Einstellungen zu SolidWorks PDM gewählt ist.

## Beispiele

**Ein neuer Typ.** Du legst einen Typ mit Rundmaterial für Deutsch und Round bar für Englisch an. Er steht sofort unter **Typ** im Rohblockformular zur Wahl, am Ende der Liste.

**Ein Typ, den du nicht mehr kaufst.** Du archivierst Flachmaterial. Rohblöcke, die ihn haben, behalten ihn, und die Typauswahl zeigt ihn zuletzt mit dem Etikett **Archiviert**. Ein späteres Wiederherstellen wird abgelehnt, wenn bis dahin ein aktiver Typ Flachmaterial heißt.

**Einen Typ nach oben schieben.** Die meisten deiner Blöcke sind Rundmaterial, also hältst du den Griff von Rundmaterial fest und ziehst ihn ganz nach oben. Das Rohblockformular bietet ihn jetzt zuerst an.
