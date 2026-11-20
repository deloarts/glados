---
title: Bestellungen
summary: Was die Bestellliste, die Zeitleiste und die Bestellseite zeigen, wie du eine Bestellung findest und wo jede Aktion an einer Bestellung erklärt ist.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/order/create_order.py
  - backend/src/modules/fulfillment/application/use_cases/order/get_order.py
  - backend/src/modules/fulfillment/application/use_cases/order/update_order.py
  - backend/src/modules/fulfillment/application/use_cases/order/set_order_supplier_order_numbers.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
lastVerified: 2026-11-20
---

Unter **Beschaffung** listet der Reiter **Bestellungen** jede Lieferantenbestellung. Eine Bestellung fasst die Positionen zusammen, die du bei einem Lieferanten kaufst, oder die Schritte eines Loses, die du zu einem Lieferanten schickst. Die meisten Bestellungen entstehen aus einer Bedarfsliste oder aus der Vergabe einer Angebotsanfrage, und **Neue Bestellung** legt eine leere mit **Lieferant** und optionaler **Notiz** an. Zum Anlegen brauchst du **Bestellungen schreiben**.

## Die Liste {#list}

Jede Zeile zeigt **Bestellnr.**, **Status**, **Lieferant**, die Anzahl der **Positionen**, **Gesamt (netto)**, die Termine **Bestellt**, **Erw. Lieferung** und **Geliefert**, den **Lagerort** und die **Notiz**. Die Lieferantenauftragsnummern einer Bestellung stehen als zweite Zeile unter ihrer **Bestellnr.**, und der Filter dieser Spalte findet eine Bestellung über jede der beiden Nummern. Klick auf eine Zeile, um ihre Positionen aufzuklappen, und auf die Bestellnummer, um die Bestellseite zu öffnen. Ein Rechtsklick auf eine Zeile zeigt die Aktionen der Bestellung. **Exportieren** speichert die gefilterten Bestellungen als Excel-Datei, siehe [Bedarfe und Bestellungen exportieren](/handbook/procurement/list-export).

Die Leiste über der Tabelle sucht nach Bestellnummer, Lieferantenauftragsnummer, Lieferant und den Artikeln auf den Positionen, etwa einem Bestellcode oder einer Losnummer. Sie sortiert nach Bestellnummer, Bestelldatum oder erwarteter Lieferung und gruppiert nach **Status** oder **Lieferant**. **Geliefert ausblenden** und **Storniert ausblenden** beschränken die Liste auf die offenen Bestellungen. Ist ein Dateispeicher eingerichtet, zeigt **Ohne Rechnung** nur die Bestellungen ohne Rechnungsdatei, und **Dateien anzeigen** fügt eine Spalte mit den Dateien jeder Bestellung hinzu.

## Die Zeitleiste {#timeline}

**Zeitleiste** zeichnet die Bestellungen als Balken vom Bestelldatum bis zum Lieferdatum, oder bis zur erwarteten Lieferung, solange nichts eingetroffen ist. Sie zeigt jede offene Bestellung und die, die in den letzten 30 Tagen geliefert oder storniert wurden, und **Geliefert ausblenden** und **Storniert ausblenden** gelten auch hier. Eine Position mit eigenen Terminen erscheint als Balken unter ihrer Bestellung. **Zurück zur Liste** führt zur Tabelle zurück.

## Die Bestellseite {#page}

Die Leiste oben zeigt den Status, den erwarteten oder tatsächlichen Liefertermin, den Lagerort, die Lieferantenauftragsnummern und die Angebotsanfragen, aus denen die Positionen stammen. Eine gelieferte Bestellung ohne Rechnungsdatei zeigt **Rechnung fehlt**. Die Schaltflächen darunter fügen Positionen und Dateien hinzu, bearbeiten die Zusatzkosten, ändern **Lieferant**, **Erwartetes Lieferdatum**, **Lagerort**, **Lieferantenauftragsnummern** und **Notiz**, markieren alle Positionen, senden Mails und stornieren die Bestellung. **Position hinzufügen** fügt ein **Kaufteil** oder eine **Virtuelle Position** für etwas hinzu, das nicht im Katalog steht. Notiz und Dateien stehen in einem Panel neben den Positionen, das **Dateien-Panel ausblenden** einklappt. Auf dem Handy zeigt die Seite nur die Positionen mit Artikel, Menge und Status.

Die Lieferantenauftragsnummern sind die Nummern, unter denen der Lieferant deine Bestellung führt, etwa auf seiner Auftragsbestätigung. Eine Bestellung kann mehrere davon tragen. In **Lieferantenauftragsnummern** tippst du eine Nummer ein und fügst sie mit Enter oder einem Komma hinzu, und das Kreuz an einer Nummer entfernt sie. Mit **Bestellungen schreiben** kannst du sie auch nach dem Bestellen noch ändern, bis die Bestellung geliefert oder storniert ist.

Wer was in welchem Status ändern darf, steht in [Lebenszyklus einer Bestellung](/handbook/procurement/order-lifecycle#permissions). Eine Aktion, die deine Berechtigungen nicht erlauben, erscheint deaktiviert, und wo die App die fehlende Berechtigung kennt, nennt ihr Tooltip sie.

## Wo jede Aktion erklärt ist

Die Status stehen in [Lebenszyklus einer Bestellung](/handbook/procurement/order-lifecycle), Anfragen, Bestellen, Verschieben, Restmenge ausbuchen und Stornieren in [Aktionen an Bestellpositionen](/handbook/procurement/order-line-actions). Der Wareneingang steht in [Eine Bestellposition als geliefert markieren](/handbook/procurement/order-item-delivery), Mails, Laufzettel, Zusatzkosten und Dateien in [Bestell-Mails, Laufzettel und Dateien](/handbook/procurement/order-documents). Wie du zuerst mehrere Lieferanten nach Preisen fragst, beschreibt [Angebotsanfragen](/handbook/procurement/quotes).

## Beispiele

**Was ist überfällig?** Schalte **Geliefert ausblenden** und **Storniert ausblenden** ein und sortiere nach erwarteter Lieferung, früheste zuerst. Die Bestellungen oben sind die, bei denen du nachfragen solltest.

**Rechnungen einsammeln.** Schalte **Ohne Rechnung** und **Storniert ausblenden** ein. Die Liste zeigt jede Bestellung ohne Rechnungsdatei, und bei den gelieferten darunter fragst du die Lieferanten nach der Rechnung.

**Wo ist dieses Teil?** Gib den Bestellcode eines Zukaufteils in die Suche ein. Die Liste zeigt jede Bestellung mit einer Position dafür, und wenn du eine Zeile aufklappst, siehst du die Position mit ihrem Status.

**Eine Auftragsbestätigung kommt.** Der Lieferant bestätigt eine bestellte Bestellung unter AB-24117. Öffne die Bestellung, wähle **Lieferantenauftragsnummern**, tipp AB-24117 ein, drück Enter und speichere. Die Nummer steht jetzt in der Liste unter der Bestellnummer, und die Suche findet die Bestellung über sie.
