---
title: Lieferanten
summary: Wie du einen Lieferanten für Bestellungen einrichtest, was Lieferzeit und EPLAN-Data-Portal-Kürzel bewirken und wie seine Bestell- und Anfragemails entstehen.
sourceRefs:
  - backend/src/modules/catalogue/domain/services/supplier_rules.py
  - backend/src/modules/catalogue/domain/services/supplier_edp_code.py
  - backend/src/modules/catalogue/application/use_cases/supplier/create_supplier.py
  - backend/src/modules/catalogue/application/use_cases/supplier/update_supplier.py
lastVerified: 2026-11-10
---

Ein Lieferant ist eine Firma, bei der du einkaufst oder Arbeit vergibst, und zugleich der Hersteller deiner Zukaufteile. Die Liste unter Ressourcen, **Lieferanten** hält seine Daten, seine Einstellungen für Bestellmails und seine Verbindung zum EPLAN Data Portal. Einträge werden archiviert, nie gelöscht, also behalten alte Bestellungen ihren Lieferanten.

## Einen Lieferanten anlegen und bearbeiten

**Lieferant erstellen** öffnet das Formular. Nur **Name** ist Pflicht, alle anderen Felder sind optional. **Firmenname (rechtlich)**, die Adresse und die Kontaktdaten funktionieren wie bei Kunden, und **Bewertung** stuft den Lieferanten mit A, B oder C ein, beginnend bei B. **UID-Nummer** ist optional, aber zwei Lieferanten, die nicht archiviert sind, dürfen sich keine teilen. Zum Anlegen und Bearbeiten brauchst du die Berechtigung **Lieferanten schreiben**, ohne sie sind die Schaltflächen deaktiviert.

**Fertigungsmethoden** nennt die Arbeiten, die der Lieferant für dich übernehmen kann, und **Artikelgruppen**, was er liefert. Die Tabelle zeigt beides als **Fertigungsmethoden** und **Artikelgruppen** und filtert danach, und **Gruppieren nach** gruppiert sie nach **Land** oder **Fähigkeit**.

## Lieferzeit

**Lieferzeit (Tage)** ist optional und muss 0 oder mehr sein. Ist sie gesetzt und wird eine Position eines Fertigungsloses bei diesem Lieferanten bestellt, erwartet der Plan die Arbeit nach so vielen Kalendertagen zurück, statt der Lieferzeiten der Schritte dieser Position. Eine Änderung plant den Zeitplan neu.

## EPLAN Data Portal

**EPLAN-Data-Portal-Kürzel** ist das Kürzel des Portals für den Hersteller, etwa SIE für Siemens. Teile aus dem Portal finden ihren Hersteller darüber. Es hat bis zu 16 Zeichen, beginnt mit einem Buchstaben oder einer Ziffer und darf danach auch Unterstriche, Punkte und Bindestriche enthalten. Es wird in Großbuchstaben gespeichert, und nur ein aktiver Lieferant darf ein Kürzel tragen. Hak **Typnummer ist Bestellnummer 1** bei einem Hersteller an, dessen Typnummer die ist, unter der du bestellst.

## Bestell- und Anfragemails {#mails}

**Bestell-E-Mail**, **Bestellsprache** und **Bestellvorlage** legen fest, wohin eine Bestellmail geht, in welcher Sprache sie geschrieben ist und welchen Text sie hat. **Vorlage bearbeiten** öffnet einen Editor, in dem du eine Variable oder eine Tabellenspalte anklickst, um sie einzufügen. Ohne Vorlage gilt der Standard aus den Einstellungen, und ohne **Bestell-E-Mail** geht die Mail an **E-Mail**.

**Anfrage-E-Mail**, **Anfragesprache** und **Anfragevorlage** machen dasselbe für Anfragen. Jedes leere Feld übernimmt stattdessen die Bestelleinstellung.

Der Abschnitt **Kontakte** des Lieferanten listet seine Leute. Ein Kontakt mit Haken bei **Bestell-Mails** erhält die Bestellmails des Lieferanten, einer mit Haken bei **Anfrage-Mails** seine Anfragen, und die Mail trägt sie unter **An** ein. Erst wenn kein Kontakt angehakt ist, geht die Mail an die Adressen oben, ein Lieferant ohne Kontakte bekommt seine Mails also dort. [Kontakte](/handbook/resources/contacts) erklärt sie.

## Archivieren und wiederherstellen

**Archivieren** und **Wiederherstellen** findest du in den Zeilenaktionen unter **Aktionen anzeigen** und im Kontextmenü der rechten Maustaste, und für beides brauchst du die Berechtigung **Lieferanten archivieren**, ohne sie sind sie deaktiviert. Das Wiederherstellen wird abgelehnt, wenn inzwischen ein anderer aktiver Lieferant dieselbe UID-Nummer hat.

## Wo Lieferanten verwendet werden

Du wählst Lieferanten als Hersteller von Zukaufteilen und Rohblöcken, bei Bestellungen und Anfragen, beim Bestellen von Bedarfen und als Standardlieferant einer Fertigungsmethode. Auch das SolidWorks-Add-in liest sie.

## Beispiele

**Festo einrichten.** Du legst Festo an, gibst fes als Kürzel ein und hakst **Typnummer ist Bestellnummer 1** an. Das Kürzel wird als FES gespeichert, und ein Teil aus dem Portal wie DFM-25-50-P-A-GF kommt mit dieser Typnummer als Bestellnummer 1 und der Bestellnummer 170851 des Portals als Bestellnummer 2.

**Eine ausgelagerte Beschichtung.** Du setzt die **Lieferzeit (Tage)** deines Beschichters auf 10. Eine bei ihm bestellte Losposition wird jetzt 10 Kalendertage nach der Bestellung zurück eingeplant, egal was ihre Schritte sagen.

**Eine Anfrage.** Bei einem Lieferanten sind nur **Bestell-E-Mail** und **Bestellsprache** ausgefüllt. Seine Anfragen gehen an diese Adresse, in dieser Sprache.
