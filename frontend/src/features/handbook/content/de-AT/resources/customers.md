---
title: Kunden
summary: Wie du einen Kunden anlegst und aktuell hältst, was Bewertung und UID-Nummer bedeuten und wo du ihn auswählst.
sourceRefs:
  - backend/src/modules/catalogue/domain/services/customer_rules.py
  - backend/src/modules/catalogue/application/use_cases/customer/create_customer.py
  - backend/src/modules/catalogue/application/use_cases/customer/update_customer.py
  - backend/src/modules/catalogue/application/use_cases/customer/restore_customer.py
lastVerified: 2026-11-10
---

Ein Kunde ist die Firma, für die du Maschinen baust. Projekte und Produkte zeigen auf ihren Kunden, darum ist die Liste unter Ressourcen, **Kunden** der eine Ort für seinen Namen, seine Adresse und seine Kontaktdaten. Einträge werden archiviert, nie gelöscht, also scheint ein Kunde, den du nicht mehr betreust, weiter bei seinen alten Projekten auf.

## Einen Kunden anlegen und bearbeiten

**Kunde erstellen** öffnet das Formular. Nur **Name** ist Pflicht, alle anderen Felder sind optional und lassen sich später ergänzen. **Firmenname (rechtlich)** ist der eingetragene Firmenname, wenn er sich vom Kurznamen unterscheidet, den du im Alltag verwendest. **Straße**, **Stadt**, **Postleitzahl** und **Land** bilden die Adresse, das Land wählst du aus einer Liste. **E-Mail**, **Telefon** und **Website** sind die Kontaktdaten.

Zum Anlegen und Bearbeiten eines Kunden brauchst du die Berechtigung **Projekte schreiben**. Ohne sie bleibt die Schaltfläche sichtbar, aber deaktiviert. Hat jemand anderer denselben Kunden gespeichert, während du das Formular offen hattest, wird dein Speichern abgelehnt, also öffne den Kunden neu und mach deine Änderung noch einmal.

Der Abschnitt **Kontakte** eines gespeicherten Kunden listet seine Leute und legt mit **Neuer Kontakt** neue an. Das sind die Kontakte des Kunden, an die die Besprechungsprotokolle seiner Projekte und Produkte gehen können, siehe [Kontakte](/handbook/resources/contacts).

## Bewertung und UID-Nummer

**Bewertung** stuft den Kunden mit A, B oder C ein, ein neuer Kunde beginnt bei B. Die Tabelle zeigt sie als farbiges Etikett: A grün, B blau und C rot.

**UID-Nummer** ist optional, und Glados prüft ihr Format nicht. An ihr unterscheidest du zwei Firmen, darum dürfen sich zwei Kunden, die nicht archiviert sind, keine teilen. Der Name darf sich wiederholen, die UID-Nummer nicht.

## Einen Kunden finden

**Suche**, die Spaltenfilter und **Sortieren nach** grenzen die Tabelle ein und ordnen sie, und **Gruppieren nach** gruppiert sie nach **Land** oder **Bewertung**. **Erstellt** und **Geändert** zeigen Datum und Person. Ein Klick auf eine Zeile öffnet die Details des Kunden, nur zum Lesen. Zum Bearbeiten schaltest du **Aktionen anzeigen** ein und nimmst den Stift der Zeile, oder du klickst die Zeile mit der rechten Maustaste an.

## Archivieren und wiederherstellen

**Archivieren** blendet den Kunden in der Tabelle aus, **Archivierte anzeigen** zeigt ihn wieder, und **Wiederherstellen** macht ihn wieder aktiv. Für beides brauchst du die Berechtigung **Projekte verwalten**, ohne sie sind beide deaktiviert. Das Wiederherstellen wird abgelehnt, wenn inzwischen ein anderer aktiver Kunde dieselbe UID-Nummer hat.

## Wo Kunden verwendet werden

Du wählst den Kunden im Formular eines Projekts, eines Produkts und eines neuen Fertigungsteils sowie im Kundenfilter der Fertigungskennzahlen. Diese Auswahlfelder bieten auch archivierte Kunden an, zuletzt gereiht und mit dem Etikett **Archiviert**, damit ältere Einträge ihren Kunden behalten. Die globale Suche findet die Projekte, Produkte und Fertigungslose eines aktiven Kunden, wenn du seinen Namen oder rechtlichen Firmennamen eingibst.

## Beispiele

**Ein neuer Kunde.** Du legst Acme Maschinenbau mit der UID-Nummer ATU12345678 an und lässt **Bewertung** auf B. Im Projektformular kannst du ihn sofort auswählen.

**Dieselbe Firma zweimal.** Ein Kollege legt Acme Maschinenbau GmbH mit der UID-Nummer ATU12345678 an. Das Speichern wird abgelehnt, weil ein aktiver Kunde diese UID-Nummer schon hat, also öffnet er stattdessen den bestehenden.

**Einen Kunden zurückholen.** Du hast einen alten Kunden archiviert, und später wurde ein neuer Eintrag mit seiner UID-Nummer angelegt. Das Wiederherstellen des alten wird abgelehnt, bis sich die UID-Nummer eines der beiden ändert.
