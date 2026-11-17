---
title: Bedarfe und Bestellungen exportieren
summary: Wie Exportieren eine Bedarfsliste oder die Bestellliste als Excel-Datei speichert, welche Zeilen und Spalten sie enthält und warum eine Bestellung zu einer Zeile pro Position wird.
sourceRefs:
  - frontend/src/shared/components/demands/demandExportColumns.ts
  - frontend/src/features/procurement/utils/boughtItemDemandsExport.ts
  - frontend/src/features/production/made-item-demands/utils/madeItemDemandsExport.ts
  - frontend/src/features/production/source-item-demands/utils/sourceItemDemandsExport.ts
  - frontend/src/features/orders/utils/ordersExport.ts
  - frontend/src/shared/spreadsheet-export/composables/useSpreadsheetExport.ts
lastVerified: 2026-11-12
---

**Exportieren** in der Leiste über den Listen **Zukaufteile Bedarf**, **Fertigungsteile Bedarf**, **Rohblock Bedarf** und **Bestellungen** speichert die Liste als Excel-Datei. Wie beim Katalogexport, siehe [Katalog exportieren](/handbook/catalogue/catalogue-export), enthält die Datei jede Zeile, die deine Suche und deine Filter übrig lassen, in deiner Sortierung, nicht nur die Seite am Bildschirm. Wer die Liste öffnen kann, kann sie auch exportieren.

## Welche Bedarfe die Datei enthält

Ein Klick auf **Exportieren** speichert die gefilterten Bedarfe. Der Pfeil neben der Schaltfläche bietet **Alle gefilterten Zeilen** und **Ausgewählte Zeilen**, und **Ausgewählte Zeilen** speichert nur die Bedarfe, die du mit Strg-Klick oder den Kästchen ausgewählt hast. Die Gruppierung wird nicht übernommen, die Datei ist eine flache Liste.

Jeder Bedarf ist eine Zeile mit seiner Nummer, seinem Status, seinem Bucket, Menge und Einheit, seinem Projekt mit Kunde und Beschreibung, dem benötigten Teil, dem gewünschten Liefertermin, wann und von wem er angelegt wurde, und seiner Notiz. Die Spalten zum Teil unterscheiden sich je Liste. Zukaufteilbedarfe zeigen Artikelname, Bestellnummer, Teilenummer und Hersteller, Fertigungsteilbedarfe Teilenummer, Revision und Fertigungsverfahren, und Rohblockbedarfe Abmessung, Material, Typ und Los. Der Status ist der des Bedarfs selbst. Die Liste kann einen genaueren zeigen, etwa wie viel schon bestellt ist, der aus den Zuordnungen kommt, und die Datei lässt Zuordnungen und Bestellungen weg. Die letzte Spalte, **Link zum Teil**, öffnet die Seite des benötigten Teils.

## Wie Bestellungen zu Zeilen werden

Die Datei der Bestellungen hat eine Zeile pro Bestellposition, damit du die Positionen in Excel filtern und summieren kannst. Nummer, Status, Lieferant und Bestelldatum der Bestellung stehen in jeder ihrer Positionen, und eine Bestellung ohne Positionen bekommt trotzdem eine eigene Zeile. Preise sind Zahlen in der Währung, die die Spaltenüberschrift nennt. Zusatzkosten und Rabatte gehören zur Bestellung, nicht zu einer Position, daher weichen die Positionssummen von **Gesamt (netto)** ab, wenn eine Bestellung welche hat. Die letzte Spalte, **Link**, öffnet die Bestellung. Die Bestellliste hat keine Zeilenauswahl, daher speichert **Exportieren** immer die gefilterten Bestellungen.

## Lange Listen

Es gelten dieselben Grenzen wie im Katalog: über 5.000 Zeilen fragt Glados zuerst nach, und über 50.000 bittet es dich, den Filter einzuschränken. Bei Bestellungen zählen die Grenzen Bestellungen, nicht Positionen.

## Beispiele

**Offene Bedarfe eines Projekts.** Du filterst die Liste **Zukaufteile Bedarf** nach dem Projekt, blendest die erfüllten aus und klickst auf **Exportieren**. Die Datei listet, was noch fehlt, mit der Bestellnummer für die Anfrage.

**Die offenen Positionen eines Lieferanten.** Du filterst **Bestellungen** nach dem Lieferanten, wählst **Geliefert ausblenden** und klickst auf **Exportieren**. Jede offene Position ist eine Zeile mit Menge, Preis und erwarteter Lieferung.
