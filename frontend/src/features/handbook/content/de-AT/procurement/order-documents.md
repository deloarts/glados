---
title: Bestell-Mails, Laufzettel und Dateien
summary: Wie du Anfrage- und Bestell-Mails sendest, was die Statusfrage nach einer Mail bewirkt und wie Laufzettel, Zusatzkosten und Bestelldateien funktionieren.
sourceRefs:
  - frontend/src/features/orders/composables/useOrderMailComposer.ts
  - backend/src/modules/fulfillment/application/use_cases/order/mark_order_item_ordered.py
  - backend/src/modules/fulfillment/application/use_cases/order/set_order_extra_costs.py
  - backend/src/modules/fulfillment/domain/services/extra_cost_rules.py
  - backend/src/modules/fulfillment/application/use_cases/order/upload_order_file.py
  - backend/src/modules/fulfillment/application/use_cases/order/_file_kind.py
  - backend/src/modules/quality/application/use_cases/print_document/print_document.py
lastVerified: 2026-11-10
---

Eine Bestellung sammelt, was zum Lieferanten geht und was zurückkommt: die Mails, die du sendest, den Laufzettel, der mit der Ware geht, die Zusatzkosten auf der Rechnung und die Dateien wie die Auftragsbestätigung. Du erreichst all das von der Bestellseite aus, die Mails und Laufzettel auch per Rechtsklick auf die Bestellung in der Bestellliste.

## Anfrage-Mail und Bestell-Mail {#mails}

**Anfrage-Mail** fragt den Lieferanten zur Bestellung an, und **Bestell-Mail** gibt sie auf. Beide öffnen **E-Mail verfassen** mit Adresse, Betreff und Text, die schon aus den Einstellungen des Lieferanten ausgefüllt sind, mit den Positionen in einer Tabelle. Die Anfrage-Mail nimmt Anfrage-Adresse, Vorlage und Sprache des Lieferanten, wo sie gesetzt sind, und sonst die für Bestellungen, siehe [Lieferanten](/handbook/resources/suppliers). Ein Lieferant ohne Vorlage nimmt den Standard aus den Einstellungen, und gibt es beides nicht, meldet die App, dass kein Template konfiguriert ist. Prüf den Text, änder ihn bei Bedarf und wähle **Senden**. Zum Senden brauchst du **E-Mails versenden**, ohne diese Berechtigung sind beide Schaltflächen mit Tooltip deaktiviert.

## Nach dem Senden {#post-send}

Sobald eine Anfrage- oder Bestell-Mail weg ist, fragt der Dialog **Mail gesendet, Status aktualisieren?**, ob du sie an den Positionen festhalten willst. **Alle als angefragt markieren** markiert jede ausstehende Position als angefragt, und **Alle als bestellt markieren** markiert jede ausstehende und angefragte Position als bestellt, was nach einer Bestell-Mail die übliche Wahl ist. Die Schaltfläche, die zu deiner Mail passt, ist hervorgehoben. **Überspringen** ändert nichts. Du kannst die Positionen später auf der Bestellseite markieren, siehe [Aktionen an Bestellpositionen](/handbook/procurement/order-line-actions#request-order). Nach einer Stornierungs-Mail fragt der Dialog nicht, weil die Bestellung schon storniert ist.

## Laufzettel {#dockets}

Klick mit der rechten Maustaste auf die Bestellung in der Bestellliste und wähle **Laufzettel drucken**, um den Laufzettel der Bestellung an seinen Drucker zu schicken, oder **Laufzettel herunterladen**, um ihn als PDF zu speichern. Beides braucht **Dokumente drucken**. Wie der Laufzettel aussieht, richtest du unter [Laufzettel](/handbook/resources/print-dockets) ein.

## Zusatzkosten {#extra-costs}

**Zusatzkosten** auf der Bestellseite öffnet eine Liste der Kosten neben den Positionen, etwa Versand, Verpackung, Zuschläge oder ein Rabatt. **Kosten hinzufügen** fügt eine Zeile mit **Art**, **Betrag** und optional **Bezeichnung** und **Notiz** hinzu, und **Position** ordnet die Kosten einer Position zu. Bleibt sie leer, zeigt sie **Ganze Bestellung**, und die Kosten gehören zur ganzen Bestellung. Der Betrag muss über null liegen, ein **Rabatt** wird abgezogen, und die Art **Sonstiges** braucht eine Bezeichnung. Die Kosten bleiben nach der Lieferung bearbeitbar, weil der Versand oft erst auf der Rechnung steht, aber eine stornierte Bestellung nimmt keine an. Sie brauchen **Bestellungen schreiben**, solange die Bestellung ein Entwurf oder angefragt ist, und danach **Bestellungen verwalten**. Eine Vergabe aus einer Angebotsanfrage bringt die Kosten des Angebots mit.

## Bestelldateien {#files}

Ist ein Dateispeicher eingerichtet, legt **Datei hinzufügen** ein PDF als **Angebot**, **Auftragsbestätigung**, **Lieferschein**, **Rechnung** oder **Allgemein** ab, oder ein Bild unter **Bilder**, und **Foto aufnehmen** nutzt die Kamera. Jede Datei darf bis zu 25 MB groß sein. Die Dateien stehen im Panel neben den Positionen, und vor dem Löschen fragt die App nach. Dateien hinzufügen und löschen braucht **Bestellungen schreiben**.

## Beispiele

**Eine Bestellung aufgeben.** Wähl bei einer Bestellung im Entwurf **Bestell-Mail**, prüf die Positionen und sende. Im nächsten Dialog wählst du **Alle als bestellt markieren**, und die Bestellung ist bestellt.

**Versand auf der Rechnung.** Die Rechnung einer gelieferten Bestellung enthält 18,50 für den Versand. Öffne **Zusatzkosten**, füg eine Zeile **Versandkosten** mit 18,50 auf die ganze Bestellung hinzu und speichere, und die Summe der Bestellung enthält sie.

**Ein Foto vom Lieferschein.** Öffne beim Wareneingang die Bestellung auf einem Tablet, wähle **Datei hinzufügen** und **Foto aufnehmen** und fotografiere den Lieferschein. Das Bild liegt dann bei der Bestellung unter **Bilder**.
