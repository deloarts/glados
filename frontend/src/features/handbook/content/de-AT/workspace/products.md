---
title: Produkte
summary: Wie die Produktliste und die Seite eines Produkts die Daten einer Maschine, ihre Projekte, Geräte, Abläufe und Dokumente enthalten, und wer ein Produkt ändern oder archivieren darf.
sourceRefs:
  - backend/src/modules/workspace/domain/services/product_rules.py
  - backend/src/modules/workspace/domain/entities/product.py
  - backend/src/modules/workspace/application/use_cases/product/update_product.py
  - backend/src/modules/workspace/application/use_cases/product/archive_product.py
  - backend/src/modules/workspace/application/use_cases/product/restore_product.py
  - backend/src/modules/workspace/application/use_cases/product/get_renumber_impact.py
  - frontend/src/features/workspace/views/ProductDetailView.vue
lastVerified: 2026-11-10
---

Workspace, **Produkte** listet die Maschinen, die ihr baut. Ein Produkt enthält die Maschinendaten für die CE-Beurteilung und seine [Projekte](/handbook/workspace/projects), und, wo diese Funktionen eingeschaltet sind, seine Geräte, Abläufe, Berechnungen und Prüflisten. Aktive Produkte erscheinen auch im Widget **Aktuelle Produkte** eines Infoscreens.

## Die Produktliste

Die Spalten filtern nach Nummer, Kunde, Beschreibung, zuständigem Benutzer, Erstelldatum und danach, ob ein Produkt **Aktiv** ist, und die Ansichtsleiste sortiert und gruppiert nach **Kunde** oder **Aktiv-Status**. Ein Klick auf eine Zeile öffnet die Seite des Produkts. **Produkt erstellen** braucht **Projekte schreiben**, und die **Produktnummer** muss zum **Muster für Produktnummer** unter Einstellungen, **Nummerierung** passen. Die Knöpfe zum Archivieren und Wiederherstellen in der Zeile brauchen **Projekte verwalten**; ohne die Berechtigung sind sie ausgegraut, und ihr Tooltip nennt sie. Archivieren macht ein Produkt auch inaktiv, und Wiederherstellen macht es nicht wieder aktiv. **Archivierte anzeigen** listet archivierte Produkte.

## Ein Produkt bearbeiten

Ein Produkt bearbeitet seine zuständige Person oder jede Person mit **Projekte verwalten**; für alle anderen ist **Produkt bearbeiten** ausgegraut, und sein Tooltip sagt, warum. Neben Nummer, Kunde und Beschreibung enthält das Formular die **Maschinendaten für die CE-Beurteilung**, die die Prüflisten des Produkts in ihren Kopf übernehmen, die **SPS-Umgebung**, für die seine Variablen gebildet werden, und seine **Gewerke**, die bestimmen, welche Pläne eine Geräteumbenennung nennt. **Rechtsgrundlage** wird aus **Geplantes Inverkehrbringen** vorbelegt. Bilder und Dokumente kommen in die Dateien des Produkts, sobald es gespeichert ist.

Änderst du die **Produktnummer**, öffnet sich vor dem Speichern **Produktnummer ändern**. Es listet die Geräte, die umbenannt werden, und warnt, dass CAD-Dateien mit der alten Nummer im CAD umbenannt werden müssen, dass freigegebene Berechnungen, Prüflisten und exportierte Berichte die alte Nummer behalten und dass externe Systeme das Produkt unter ihr nicht mehr finden. **Nummer ändern** speichert.

## Die Seite eines Produkts

Die **Übersicht** zeigt die Details, die Maschinendaten und Links zu den dazugehörigen Einträgen. **Projekte** listet die Projekte des Produkts, und **Stückliste**, **Bestellungen** und **Kosten** fassen sie alle zusammen. **Dateien** erscheint, solange die Dateiablage eingeschaltet ist. **Geräte**, **Abläufe**, **Berechnungen** und **Prüflisten** erscheinen, solange diese Funktionen eingeschaltet sind; siehe [Geräte eines Produkts](/handbook/workspace/product-devices), [Abläufe](/handbook/workspace/flow-sequences) und [Revisionen und Freigabe](/handbook/workspace/document-revisions). Geräte und Abläufe eines archivierten Produkts lassen sich nicht mehr ändern.

## Beispiele

**Ein neuer Maschinentyp.** Du legst Produkt M-2045 für einen Kunden an, hakst unter **Gewerke** Pneumatik und Elektrik an und legst dann sein erstes Projekt an.

**Eine vertippte Nummer.** M-2054 sollte M-2045 heißen. **Produktnummer ändern** zeigt, dass sich damit zwölf Gerätenamen ändern, und du benennst die CAD-Dateien mit der alten Nummer um.

**Eine Maschine, die nicht mehr gebaut wird.** Jemand mit **Projekte verwalten** archiviert das Produkt. Es verschwindet aus der Liste und von den Infoscreens, und **Archivierte anzeigen** findet es weiterhin.
