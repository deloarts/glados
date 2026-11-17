---
title: EPLAN Data Portal
summary: Wie Glados Kaufteile aus dem EPLAN Data Portal füllt, beim Anlegen und später bei einem vorhandenen Teil, und was mit Teilen passiert, die PDM verwaltet.
sourceRefs:
  - backend/src/modules/external_data/application/services/edp_item_draft.py
  - backend/src/modules/external_data/application/use_cases/eplan_data_portal/edp_lookup.py
  - backend/src/modules/external_data/application/use_cases/eplan_data_portal/fill_edp_picture.py
  - backend/src/modules/catalogue/domain/services/supplier_edp_code.py
  - backend/src/modules/external_data/domain/entities/admin_settings/eplan_data_portal.py
lastVerified: 2026-11-13
---

Das EPLAN Data Portal ist der Katalog von EPLAN mit Herstellerteilen. Hat dein Administrator es eingeschaltet, kann Glados ein Kaufteil daraus füllen: Artikelname, Bestellnummer und Typnummer, EAN, einen Link zur Herstellerseite, den Hersteller, die Produktfamilie und das Produktbild. Masse, Zolltarifnummer und Preis stehen nicht im Portal, die trägst du weiter selbst ein.

## Ein Teil aus dem Portal anlegen

Gib im Anlegen-Dialog bei **Aus dem EPLAN Data Portal füllen** eine Bestellnummer, einen Typ, eine EPLAN-Artikelnummer oder einen Namen ein und wähl ein Teil aus der Liste. Die Felder darunter werden gefüllt, und du kannst sie vor dem Speichern noch ändern. Ist das Teil schon im Katalog, sagt dir der Dialog das, damit du es nicht doppelt anlegst. Das neue Teil wird mit dem Portal verknüpft, und wenn die Dateiablage eingeschaltet ist, kommt sein Bild kurz danach. Es bekommt die **Standard-Artikelgruppen** aus den Data-Portal-Einstellungen, und sein Artikelname wird in der dort eingestellten **Sprache des Artikelnamens** übernommen, oder in der anderen Sprache, wenn das Portal keinen hat.

Für die Suche im Portal brauchst du die Berechtigung **EPLAN Data Portal verwenden**, zum Speichern des Teils weiterhin **Zukaufteile schreiben**. Fehlt dir die erste, ist das Suchfeld deaktiviert, sein Tooltip nennt die Berechtigung, und Teilebilder zeigen einen Platzhalter. Zum Abgleichen eines vorhandenen Teils brauchst du nur **Zukaufteile schreiben**.

## Den Hersteller zuordnen

Ein Teil findet seinen Hersteller nur über das **EPLAN-Data-Portal-Kürzel** des Lieferanten, zum Beispiel SIE für Siemens oder FES für Festo. Es wird einmal im Lieferantenformular eingetragen. Hat kein Lieferant das Kürzel, lässt Glados den Hersteller leer und sagt dir, welches Kürzel fehlt. Normalerweise wird die Bestellnummer des Portals zur **Bestellnummer 1** und seine Typnummer zur **Bestellnummer 2**. Bei einem Hersteller, der nach Typnummer bestellt, etwa Festo, setzt du beim Lieferanten den Haken bei **Typnummer ist Bestellnummer 1**, und die beiden tauschen, zum Beispiel DFM-25-50-P-A-GF als Bestellnummer 1 und 170851 als Bestellnummer 2.

## Ein vorhandenes Teil abgleichen

Auf der Seite eines Kaufteils findet **Im Data Portal abgleichen** das Teil im Portal über seine Verknüpfung oder seine Bestellnummer und vergleicht beide Feld für Feld. Kennt das Portal mehrere Teile unter dieser Nummer, wählst du eines aus. Felder, in denen das Portal abweicht, sind angehakt; die Übernehmen-Schaltfläche, zum Beispiel **2 Felder übernehmen**, schreibt die angehakten, und **Nur verknüpfen** verknüpft das Teil, ohne es zu ändern. In beiden Fällen wird das Produktbild zum Data-Portal-Bild des Teils. Es steht neben einem Foto, das jemand hochgeladen hat, und neben dem CAD-Rendering aus dem PDM und ersetzt keines davon. Angezeigt wird zuerst ein Foto, dann das Data-Portal-Bild, dann das CAD-Rendering. Verknüpfst du das Teil mit einem anderen Portalteil, kommt dessen Bild, und entfernst du die Verknüpfung, verschwindet es.

## Teile, die PDM verwaltet

Bei einem Teil aus SolidWorks PDM siehst du die Felder, die PDM verwaltet, kannst sie aber nicht übernehmen. Ändere sie in der SolidWorks-Datei, dann kommen sie mit der nächsten Freigabe. Die Produktfamilie und die Verknüpfung mit dem Portal kannst du hier trotzdem setzen.

## Beispiele

**Ein neues Schütz.** Du tippst 3RT2015 und wählst das Siemens-Schütz. Name, Bestellnummern, EAN, Link und Siemens als Hersteller werden gefüllt, und die Produktfamilie Contactors wird gesetzt, weil es sie in Glados gibt.

**Ein altes Teil mit kurzem Namen.** Ein Webteil heißt „Schütz“. Der Abgleich zeigt die volle Bezeichnung aus dem Portal; du übernimmst nur den Artikelnamen.

**Ein Teil aus PDM.** Der Abgleich zeigt einen anderen Artikelnamen, aber du kannst ihn nicht anhaken. Die Konstruktion korrigiert ihn in der SolidWorks-Datei.
