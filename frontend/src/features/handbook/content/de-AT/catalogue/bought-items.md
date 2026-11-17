---
title: Zukaufteile
summary: Was der Zukaufteilkatalog enthält, was du in seiner Liste und auf der Seite eines Teils tun kannst und welche Felder PDM verwaltet, sobald es ein Teil kennt.
sourceRefs:
  - frontend/src/features/bought-items/components/BoughtItemsCatalogueControls.vue
  - frontend/src/features/bought-items/composables/useBoughtItemsCatalogueContextMenu.ts
  - frontend/src/features/catalogue/views/BoughtItemDetailView.vue
  - backend/src/modules/catalogue/domain/policies/pdm_ownership.py
  - backend/src/modules/catalogue/domain/policies/catalogue_item_status.py
lastVerified: 2026-11-12
---

Der Zukaufteilkatalog listet jedes Teil, das du bei einem Lieferanten kaufst, etwa Schütze, Zylinder und Schrauben. Jedes Teil ist eine Zeile, gefunden über Hersteller und Bestellnummer, und jeder Bedarf und jede Bestellposition für das Teil zeigt darauf. Die Liste ist der Reiter **Zukaufteile** im Katalog, und ein Klick auf eine Zeile öffnet die eigene Seite des Teils.

## In der Liste arbeiten

**Neu** legt ein Teil in einem Dialog an, in dem **Aus dem EPLAN Data Portal füllen** die Felder für dich füllen kann, siehe [EPLAN Data Portal](/handbook/catalogue/eplan-data-portal). **Aus Datei importieren** legt viele Teile aus einer Tabelle an, siehe [Kaufteile aus Datei importieren](/handbook/catalogue/bought-item-import). Beide sind ausgeblendet, wenn deine Nummerierungseinstellungen das Anlegen von Zukaufteilen im Web nicht erlauben. **Bearbeiten** schaltet die Liste in den Bearbeitungsmodus, in dem du mehrere Zeilen auswählst und ein Feld für alle auf einmal änderst. **Exportieren** speichert die gefilterte Liste als Excel-Datei, siehe [Katalog exportieren](/handbook/catalogue/catalogue-export).

Das Zeilenmenü bietet **Bearbeiten**, **Kopieren**, **Zusammenführen**, **Archivieren** oder **Wiederherstellen**, **Bedarf anlegen**, **Zur Bestellung hinzufügen**, **Bestellhistorie anzeigen**, **Änderungsprotokoll anzeigen** und **Etikett drucken**. **Zusammenführen** verschiebt Bedarfe, Bestellpositionen, Artikelgruppen und Dateien eines Teils zu einem anderen und archiviert es; das brauchst du, wenn dasselbe Teil zweimal angelegt wurde. Bearbeiten und Kopieren brauchen **Zukaufteile schreiben**, Zusammenführen und Archivieren brauchen **Zukaufteile archivieren**. **PDM-Vorschau** erscheint, wenn PDM angebunden ist, und listet die Dateien im Vault, die der Katalog noch nicht eingeholt hat.

## Die Seite eines Teils

Die Seite zeigt das Teil mit seinen Bildern und Feldern, seine **Bedarfe**, seine **Bestellungen**, seine **Dateien**, seine **Verwendung** in Projekten und sein **Änderungsprotokoll**. Oben kannst du **Artikel bearbeiten**, **Im Data Portal abgleichen**, wenn das Data Portal eingeschaltet ist, **Bedarf anlegen**, **Zur Bestellung hinzufügen** und mit **Drucken** ein Etikett oder einen Laufzettel drucken. Jede Aktion braucht ihre eigene Berechtigung, **Zukaufteile schreiben**, **Bedarfsteile schreiben**, **Bestellungen schreiben** oder **Dokumente drucken**, und ist ohne sie ausgegraut.

## Status und PDM

Ein Teil ist **Aktiv**, **Inaktiv** oder **Ersetzt**, und nur ein aktives Teil kann in einem neuen Bedarf oder einer neuen Bestellposition stehen, siehe [Lebenszyklus eines Katalogartikels](/handbook/catalogue/catalogue-item-lifecycle). Ein im Web angelegtes Teil zeigt **Web** als **Datenquelle**. Liefert PDM eine Datei, die dazu passt, über Teilenummer, GTIN oder Hersteller und Bestellnummer, übernimmt PDM das Teil, und seine **Datenquelle** zeigt ab dann **PDM**. Ein übernommenes Teil bleibt das für immer. Seine Artikeldaten und sein Status kommen dann aus PDM, der Bearbeiten-Dialog zeigt diese Felder gesperrt mit „Von PDM verwaltet", und du änderst sie in der SolidWorks-Datei. Hat dein Administrator diese Sperre aufgehoben, fragt Glados vor dem Bearbeiten nach, weil PDM die Änderung überschreiben kann. Produktfamilie, Liefertoleranzen und Dateien bleiben bei dir.

## Beispiele

**Ein neues Teil.** Du brauchst ein Schütz, das nicht im Katalog ist. **Neu**, eine Suche im Data Portal und **Speichern** legen es an, und **Bedarf anlegen** auf seiner Seite fordert es für dein Projekt an.

**Dasselbe Teil zweimal.** Jemand hat denselben Zylinder noch einmal von Hand angelegt. Du führst das Duplikat mit **Zusammenführen** ins Original, und seine Bedarfe und Bestellpositionen wandern mit.

**Ein Teil, das PDM kennt.** Eine Konstrukteurin hat dein Webteil in eine Baugruppe eingebaut. Nach der nächsten Freigabe zeigt seine Datenquelle **PDM**, und sein Artikelname lässt sich nur noch in der SolidWorks-Datei ändern.
