---
title: Rohblöcke
summary: Was ein Rohblock ist, wie Typ, Abmessung und Material das Rohmaterial beschreiben und wie Lose, Bedarfe und Bestellungen ihn nutzen.
sourceRefs:
  - frontend/src/features/source-items/components/SourceItemsCatalogueControls.vue
  - frontend/src/features/source-items/components/SourceItemCreateForm.vue
  - frontend/src/features/source-items/components/SourceItemsCatalogueTable.vue
  - frontend/src/features/catalogue/views/SourceItemDetailView.vue
  - backend/src/modules/catalogue/domain/policies/catalogue_item_status.py
lastVerified: 2026-11-10
---

Ein Rohblock beschreibt das Rohmaterial, aus dem ein Fertigungsteil entsteht, zum Beispiel eine Stahlstange rund 40 mm in 1.0037 oder eine Aluminiumplatte. Ein Fertigungsteil nennt ihn als Materialquelle, und jedes Los dieses Teils braucht ihn dann als Rohmaterial, siehe [Lebenszyklus eines Rohblock-Bedarfs](/handbook/procurement/source-item-demand-lifecycle). Die Liste ist der Reiter **Rohblock** im Katalog. Rohblöcke gehören allein Glados, PDM ändert sie also nie, das SolidWorks-Add-in kann aber auch einen anlegen.

## Einen Rohblock anlegen

**Neu** öffnet **Rohblock erstellen**. Wähl den **Typ**, beschreib die **Abmessung** über ihre Form, **Block**, **Profil**, **Drehteil**, **Rohr** oder **Benutzerdefiniert**, und gib das **Material** ein. **Masse [g]**, **Hersteller**, **Bestellnummer 1**, **Bestellnummer 2** und **Notiz** sind optional. **Ähnliche Artikel** zeigt beim Tippen vorhandene Rohblöcke mit gleichem Typ und Material, damit du einen davon verwenden kannst. Ein Rohblock mit demselben Typ, derselben Abmessung und demselben Material wie ein vorhandener wird abgelehnt, und der Dialog bietet an, den vorhandenen zu bearbeiten. Die Typen selbst pflegst du unter Ressourcen, siehe [Rohblocktypen](/handbook/resources/source-item-types).

Du kannst einen Rohblock auch anlegen, während du die Materialquelle eines Fertigungsteils wählst: Die Auswahl bietet **Rohblock erstellen** an, und gibt es schon einen identischen, wird dieser verwendet.

## In der Liste und auf der Seite arbeiten

**Bearbeiten** schaltet die Liste in den Bearbeitungsmodus, um mehrere Rohblöcke auf einmal zu ändern. Das Zeilenmenü bietet **Bearbeiten**, **Etikett drucken**, **Archivieren** oder **Wiederherstellen** und **UUID kopieren**. Bearbeiten braucht **Rohblock schreiben**, Archivieren **Rohblock archivieren**, und ohne die Berechtigung sind die Aktionen ausgegraut.

Die Seite eines Rohblocks zeigt ihn mit seinen **Dateien**, den **Bestellungen** und **Bedarfen**, die ihn nennen, samt ihren Losen, seine **Verwendung** und sein **Änderungsprotokoll**. **Bedarf anlegen** und **Zur Bestellung hinzufügen** bleiben dort ausgegraut, weil ein Rohblock-Bedarf über die Materialquelle eines Loses angelegt und das Material über seine Bedarfe bestellt wird.

## Status

Ein Rohblock ist **Aktiv**, **Inaktiv** oder **Ersetzt** wie jeder Katalogartikel, und nur ein aktiver kann als neue Materialquelle gewählt werden oder einen neuen Bedarf bekommen. Ein ersetzter Rohblock nennt seinen **Nachfolgeartikel**, siehe [Lebenszyklus eines Katalogartikels](/handbook/catalogue/catalogue-item-lifecycle).

## Beispiele

**Eine neue Stange.** Du legst Typ Rundstange an, ein **Drehteil** mit 40 mm Durchmesser und 3000 mm Länge, Material 1.0037. Er kann jetzt als Materialquelle gewählt werden.

**Dieselbe Stange noch einmal.** Ein Kollege gibt denselben Typ, dieselbe Abmessung und dasselbe Material ein. Das Anlegen wird abgelehnt, und **Bestehenden Artikel bearbeiten** öffnet den, den du angelegt hast.

**Ein Material, das nicht mehr gekauft wird.** Du setzt die alte Stange auf **Ersetzt** und nennst die neue als Nachfolger. Die alte Stange kann für neue Arbeit nicht mehr gewählt werden, Lose, die sie schon verwenden, laufen weiter.
