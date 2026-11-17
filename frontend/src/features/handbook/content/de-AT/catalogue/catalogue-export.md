---
title: Katalog exportieren
summary: Wie Exportieren die Liste der Zukauf- oder Fertigungsteile als Excel-Datei speichert, welche Zeilen und Spalten die Datei enthält und was bei einer sehr langen Liste passiert.
sourceRefs:
  - frontend/src/shared/spreadsheet-export/components/SpreadsheetExportButton.vue
  - frontend/src/shared/spreadsheet-export/composables/useSpreadsheetExport.ts
  - frontend/src/shared/spreadsheet-export/utils/fetchExportRows.ts
  - frontend/src/features/bought-items/utils/boughtItemsCatalogueExport.ts
  - frontend/src/features/made-items/utils/madeItemsCatalogueExport.ts
lastVerified: 2026-11-12
---

**Exportieren** in der Leiste über der Liste der Zukaufteile und der Fertigungsteile speichert die Liste als Excel-Datei. Die Datei enthält, was du siehst: die Zeilen, die deine Suche und deine Filter übrig lassen, in deiner Sortierung, mit den Spalten, die du eingeblendet hast. Wer die Liste öffnen kann, kann sie auch exportieren, und die Datei wird wie jede andere heruntergeladen.

## Welche Zeilen die Datei enthält

Ein Klick auf **Exportieren** speichert jede Zeile des aktuellen Filters, nicht nur die Seite am Bildschirm. Deine Suche, die Spaltenfilter, die Sortierung, **Archivierte anzeigen** und bei Fertigungsteilen **Alle Revisionen anzeigen** zählen mit. Der Pfeil neben der Schaltfläche bietet **Alle gefilterten Zeilen** und **Ausgewählte Zeilen**. **Ausgewählte Zeilen** speichert nur die Zeilen, die du angehakt hast, praktisch für eine kurze Liste, die du von Hand zusammenstellst. Zum Anhaken brauchst du **Zukaufteile schreiben** oder **Fertigungsteile schreiben**. Die Gruppierung wird nicht übernommen, die Datei ist immer eine flache Liste.

## Welche Spalten die Datei enthält

Die Datei hat die Spalten, die die Liste zeigt, in derselben Reihenfolge, also bestimmt **Spalten** in der Ansichtsleiste, was hineinkommt. Jeder Wert behält seine Art. Datumsangaben sind echte Datumswerte, die du in Excel sortieren und filtern kannst, Mengen sind Zahlen, und Teilenummern, Bestellnummern und GTINs bleiben Text, damit ihre führenden Nullen erhalten bleiben. Status und Datenquelle zeigen ihre Bezeichnung, Gruppen und Produktfamilien ihre Namen. Neben **Erstellt** und **Geändert** ergänzt die Datei, wer das Teil angelegt oder zuletzt geändert hat. Die letzte Spalte, **Link**, öffnet die Seite des Teils in Glados, wo auch seine Bilder und Dateien sind, denn eine Tabelle kann sie nicht aufnehmen. Die Liste der Fertigungsteile lässt deshalb ihre Bild- und Dateispalte weg, und die Liste der Zukaufteile zählt die PDF-Dateien.

## Lange Listen

Bis 5.000 Zeilen wird die Datei sofort heruntergeladen. Darüber fragt Glados zuerst nach, weil das Lesen der Zeilen einen Moment dauert. Während es liest, zeigt die Schaltfläche, wie weit es ist, und **Abbrechen** hält es an, ohne etwas herunterzuladen. Über 50.000 Zeilen startet Glados nicht und bittet dich, den Filter einzuschränken.

## Beispiele

**Eine Liste für einen Lieferanten.** Du filterst die Zukaufteile nach dem Hersteller, blendest die Bestellnummern ein und klickst auf **Exportieren**. Du schickst dem Lieferanten eine Tabelle mit einer Zeile pro Teil, und die Spalte **Link** führt dich zu jedem Teil zurück.

**Eine Handvoll Teile.** Du hakst in der Liste sechs Fertigungsteile an und wählst **Ausgewählte Zeilen**. Die Datei enthält genau diese sechs, ohne den Rest der Liste zu lesen.

**Der ganze Katalog.** Die Liste zeigt 12.430 Zukaufteile. Glados fragt vor dem Start nach, du bestätigst, und der Download folgt, sobald alle Zeilen gelesen sind.
