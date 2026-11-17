---
title: Produktfamilien
summary: Was eine Produktfamilie ist, wie sie sich von einer Artikelgruppe unterscheidet und wie du sie bei einem Kaufteil setzt.
sourceRefs:
  - backend/src/modules/catalogue/application/use_cases/product_family/create_product_family.py
  - backend/src/modules/catalogue/domain/services/product_family_rules.py
  - backend/src/modules/catalogue/application/services/catalogue_list_order.py
  - backend/src/modules/catalogue/application/services/product_family_lookup.py
  - backend/src/modules/external_data/application/services/edp_item_draft.py
lastVerified: 2026-11-10
---

Eine Produktfamilie ist die Produktart des Herstellers, etwa Zylinder, Ventile oder Schütze. Mit ihr findest du alle Teile einer Art schnell im Kaufteilkatalog. Artikelgruppen sind deine eigene Einkaufsgliederung, und ein Teil kann mehrere haben; eine Produktfamilie ist die Sicht des Herstellers, und ein Teil hat höchstens eine.

## Die Liste verwalten

Die Liste findest du unter Ressourcen, **Produktfamilien**. Jede Familie hat einen **Name**, eine **Beschreibung** und eine **Label-Farbe** mit einer **Schriftfarbe**, so erscheint sie bei den Teilen. Ist die Kombination schwer lesbar, zeigt das Formular „Diese Farbkombination ist in Etikettengröße schwer lesbar.“ und bietet **Lesbare Schriftfarbe verwenden** an, das Schwarz oder Weiß für die Schrift wählt. Ein Name darf nur bei einer Familie vorkommen, die nicht archiviert ist.

Produktfamilien haben keine eigenen Berechtigungen. Anlegen, Bearbeiten, Verschieben, Archivieren und Wiederherstellen einer Familie braucht **Artikelgruppen schreiben**. Ohne sie sind die Schaltflächen deaktiviert.

In der Reihenfolge der Liste bieten die Auswahlfelder die Familien an, also stell die meistverwendeten nach oben. Darfst du Produktfamilien bearbeiten, zeigt die erste Spalte in jeder Zeile einen Griff. Halt den Griff fest und zieh die Zeile an ihren neuen Platz; eine Linie zeigt, wo sie landet. Der Griff erscheint nur, solange keine Sortierung, Suche und kein Filter aktiv ist, weil die Zeilen dann in einer anderen Reihenfolge stehen. Eine neue Familie kommt ans Ende der Liste.

## Bei einem Teil setzen

Wähl die Familie im Formular des Teils unter **Produktfamilie**. Archivierte Familien werden nicht angeboten, aber ein Teil, das schon eine hat, behält sie. Die Familie lässt sich auch bei Teilen setzen, die aus SolidWorks PDM kommen. Im Kaufteilkatalog zeigt die Spalte **Produktfamilie** sie an und filtert danach.

## Aus dem EPLAN Data Portal

Wird ein Teil aus dem EPLAN Data Portal gefüllt, bekommt es die Familie, die so heißt wie die Produktgruppe im Portal, Groß- und Kleinschreibung egal. Eine Familie, die es noch nicht gibt, wird nicht angelegt; leg sie hier an, und der nächste Abgleich findet sie.

## Beispiele

**Zylinder zusammenfassen.** Leg die Familie Zylinder an und setz sie bei deinen Festo-Zylindern. Filterst du den Katalog nach Zylinder, siehst du sie alle, egal welche Artikelgruppen sie haben.

**Eine umbenannte Familie.** Du benennst Zylinder in Pneumatikzylinder um. Jedes Teil behält sie, weil das Teil auf die Familie zeigt und nicht auf ihren Namen.
