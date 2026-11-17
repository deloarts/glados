---
title: Kaufteile aus Datei importieren
summary: Wie du viele Kaufteile aus einer Excel-Tabelle anlegst, was dir die Prüfung zu jeder Zeile sagt und wie der Abgleich mit dem EPLAN Data Portal Zeilen für dich füllt.
sourceRefs:
  - backend/src/modules/external_data/application/use_cases/bought_item_import/batch_create_items.py
  - backend/src/modules/external_data/application/use_cases/bought_item_import/_import_rows.py
  - backend/src/modules/catalogue/domain/services/data_import_profiles.py
  - backend/src/modules/catalogue/domain/policies/order_code.py
  - frontend/src/shared/spreadsheet-import/components/SpreadsheetColumnNamesButton.vue
lastVerified: 2026-11-10
---

**Aus Datei importieren** im Kaufteilkatalog legt für jede Zeile einer Excel-Tabelle ein Kaufteil an. Du lädst die Datei hoch, prüfst jede Zeile, und die Anlegen-Schaltfläche, zum Beispiel **3 Teile anlegen**, legt die Teile an, die bereit sind. Vorher wird nichts angelegt.

## Die Datei vorbereiten

Die Tabelle braucht eine Kopfzeile mit einer Spalte pro Feld. Glados findet die Kopfzeile selbst und erkennt die Spaltennamen, die ein Administrator unter Einstellungen, Datenimport festgelegt hat, auf Deutsch oder Englisch. **Spaltennamen** zeigt jeden Namen, den Glados für jedes Feld erkennt. Wird eine Pflichtspalte nicht erkannt, wählst du für diesen Upload selbst die Spalte für jedes Feld.

Ohne Abgleich braucht jede Zeile einen **Artikelname**, eine **Bestellnummer** und einen **Hersteller**. Der Hersteller muss der Name eines vorhandenen Lieferanten sein, Groß- und Kleinschreibung egal. Alles andere ist optional. **Artikelgruppen** dürfen mehrere Namen enthalten, getrennt durch Strichpunkt oder Beistrich, jeder Name in einer beliebigen Sprache der Gruppe. **Masse (g)** ist eine ganze Zahl in Gramm. Eine Datei darf höchstens so viele Zeilen haben, wie die Einstellungen erlauben, 100, solange dein Administrator nichts anderes eingestellt hat.

## Im EPLAN Data Portal abgleichen

Ist das Data Portal eingeschaltet, setz vor dem Hochladen den Haken bei **Im EPLAN Data Portal abgleichen**. Dann reicht pro Zeile eine Bestellnummer oder eine EPLAN-Artikelnummer. Das Portal füllt Artikelname, Bestellnummern, EAN, einen Link, den Hersteller und die Produktfamilie, und wo deine Datei etwas anderes sagt, gewinnt das Portal und die Zeile zeigt es dir. Masse, Zolltarifnummer und Notizen kommen weiter aus der Datei. Ein Teil, dessen Hersteller keinen Lieferanten mit seinem EPLAN-Data-Portal-Kürzel hat, ist ungültig, bis das Kürzel beim Lieferanten eingetragen ist.

## Die Prüfung lesen

Jede Zeile zeigt einen Status. Zeilen mit **Bereit** werden angelegt. **Vorhanden** heißt, das Teil ist schon im Katalog, gefunden über GTIN, EAN oder Hersteller und Bestellnummer; es wird nicht importiert und die Zeile zeigt, wo die Datei abweicht. **Doppelt** wiederholt eine frühere Zeile. **Unbekannter Bezug** nennt einen Hersteller, eine Artikelgruppe oder Produktfamilie, die Glados nicht kennt. **Nicht gefunden** und **Mehrdeutig** gibt es nur beim Abgleich: Wähl das richtige Teil oder leg die Zeile aus der Datei an. **Ungültig** sagt, was fehlt oder warum das Teil nicht angelegt werden konnte, zum Beispiel eine GTIN, die ein anderes Teil schon hat. Bearbeite oder entferne eine Zeile und drück noch einmal **Prüfen**.

## Die Teile anlegen

Die Anlegen-Schaltfläche legt alle bereiten Zeilen auf einmal an. Mit Abgleich verknüpft sie außerdem die vorhandenen Teile mit ihrem Teil im Data Portal. Diese Zeilen verlassen den Entwurf, die übrigen warten auf den nächsten Versuch. Solange ein Entwurf wartet, zeigt die Schaltfläche im Katalog eine Markierung mit „Ein unfertiger Import wartet.", und **Entwurf verwerfen** wirft die Zeilen weg.

## Beispiele

**Eine einfache Tabelle.** Drei Festo-Zylinder mit Name, Bestellnummer und Festo als Hersteller. Alle drei sind bereit, und **3 Teile anlegen** legt sie an.

**Eine mehrdeutige Nummer.** Mit Abgleich passt eine Siemens-Bestellnummer zu zwei Teilen. Wähl in der Zeile das richtige, prüf noch einmal, und die Zeile ist bereit.

**Ein Teil, das du schon hast.** Die Bestellnummer einer Zeile ist 3RT2015 1BB41, und im Katalog steht 3RT2015-1BB41 vom selben Hersteller. Die Zeile zeigt Vorhanden, weil Groß- und Kleinschreibung, Leerzeichen, Bindestriche, Punkte, Schrägstriche und Unterstriche nicht zählen, und es wird nichts angelegt.
