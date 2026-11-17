---
title: Aktionen an Bestellpositionen
summary: Wie du Bestellpositionen anfragst, bestellst, verschiebst, entfernst, mit Restmenge ausbuchst und stornierst, wie du eine ganze Bestellung stornierst und wann welche Aktion angeboten wird.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/application/use_cases/order/mark_order_item_ordered.py
  - backend/src/modules/fulfillment/application/use_cases/order/mark_order_item_ready_for_pickup.py
  - backend/src/modules/fulfillment/application/use_cases/order/move_order_item.py
  - backend/src/modules/fulfillment/application/use_cases/order/delete_order_item.py
  - backend/src/modules/fulfillment/application/use_cases/order/close_order_item_short.py
  - backend/src/modules/fulfillment/application/use_cases/order/reopen_order_item.py
  - backend/src/modules/fulfillment/application/use_cases/order/cancel_order_item.py
lastVerified: 2026-11-10
---

Klick mit der rechten Maustaste auf eine Position auf der Bestellseite oder in der aufgeklappten Zeile der Bestellliste, um zu sehen, was du mit ihr machen kannst. Das Menü graut die Aktionen aus, die der Status der Position nicht erlaubt. Eine Aktion, die deine Berechtigungen nicht erlauben, ist ebenfalls ausgegraut, und ihr Tooltip nennt die fehlende Berechtigung, siehe [Lebenszyklus einer Bestellung](/handbook/procurement/order-lifecycle#permissions).

## Anfragen, bestellen und abholen {#request-order}

**Als angefragt markieren** hält fest, dass du den Lieferanten zu einer ausstehenden Position gefragt hast. **Als bestellt markieren** hält fest, dass du eine ausstehende oder angefragte Position bestellt hast. Auf der Bestellseite machen **Alle als angefragt markieren** und **Alle als bestellt markieren** dasselbe für jede Position, die es annimmt. Nach einer [Anfrage- oder Bestell-Mail](/handbook/procurement/order-documents#mails) bietet dir die App dieselbe Wahl an.

**Als abholbereit markieren** gilt für eine bestellte oder teilweise gelieferte Position, die ein Datum bei **Erw. Abholung** hat und noch nicht markiert ist. Es hält fest, dass die Ware jetzt bereitsteht, und die Position zeigt ein Häkchen mit der Uhrzeit. Eine Position für ein Los plant die nächsten Schritte des Loses dann ab diesem Zeitpunkt.

## Positionen verschieben und entfernen {#move}

**In andere Bestellung verschieben** bringt eine ausstehende, angefragte oder bestellte Position, auf der nichts geliefert oder zurückgewiesen wurde, in eine andere offene Bestellung. Wähl die **Zielbestellung**. Hat diese Bestellung einen anderen Lieferanten, übernimmt die Position ihn. Eine schon bestellte Position liegt noch beim alten Lieferanten, deshalb warnt dich der Dialog und verschiebt sie erst, wenn du das Kästchen anhakst, dass du die Bestellung mit diesem Lieferanten selbst klärst. Zum Verschieben brauchst du **Bestellungen schreiben**, solange beide Bestellungen im Entwurf oder in der Anfrage sind, und zusätzlich **Bestellungen verwalten**, sobald die Position oder eine der Bestellungen weiter ist, siehe [Wer was ändern darf](/handbook/procurement/order-lifecycle#permissions).

**Position entfernen** löscht eine ausstehende oder angefragte Position, und ihre Bedarfe sind wieder offen. Eine bestellte Position stornierst du stattdessen.

## Restmenge ausbuchen {#close-short}

Liefert der Lieferant den Rest nicht mehr, nutze **Restmenge ausbuchen** bei einer bestellten oder teilweise gelieferten Position, auf der schon etwas eingetroffen ist. Die Menge der Position sinkt auf das Eingetroffene, die Position ist also geliefert, und ihre Bedarfe schrumpfen auf die angenommenen Teile, beginnend beim neuesten Bedarf, damit der fehlende Teil bei ihnen wieder sichtbar wird.

Schickt der Lieferant den Rest doch noch, oder braucht eine Lieferung eine [Korrektur](/handbook/procurement/delivery-correction), nutze **Position wieder öffnen**. Die Menge geht auf den alten Wert zurück, und die Position wartet wieder auf den Rest. Eine Position einer stornierten Bestellung und eine Position für ein Los lassen sich nicht wieder öffnen. Bei einer Losposition, deren Restmenge ausgebucht wurde, bleiben die fehlenden Teile offen, und die Losposition bietet für den Rest wieder **Extern vergeben** oder **Intern vergeben** an.

## Eine Position stornieren {#cancel-line}

**Position stornieren** storniert eine ausstehende, angefragte oder bestellte Position, auf der noch nichts eingetroffen ist. Ihre Bedarfe verlieren die Zuordnung und zeigen diesen Teil wieder als offen.

## Eine Bestellung stornieren {#cancel}

**Bestellung stornieren** geht, bis die Bestellung geliefert ist, und über angefragt hinaus brauchst du dafür **Bestellungen verwalten**. Gelieferte Positionen bleiben, wie sie sind, teilweise gelieferte werden beim Eingetroffenen mit Restmenge ausgebucht, und die übrigen werden storniert und geben ihre Bedarfe frei. Mit **E-Mails versenden** fragt die App dann **Lieferant benachrichtigen?** und stellt die Stornierungs-Mail zusammen.

## Beispiele

**Eine halb gelieferte Bestellung stornieren.** Position A hat 10 von 10, Position B 4 von 10, Position C nichts. **Bestellung stornieren** lässt A geliefert, bucht bei B die Restmenge bei 4 aus und storniert C, deren Bedarfe wieder offen sind.

**Eine Position auf der falschen Bestellung.** Du hast 20 Schrauben auf der Bestellung von Lieferant A gebucht und schon bestellt, aber Lieferant B soll sie liefern. Verschieb die Position in die Entwurfsbestellung von Lieferant B, hak die Bestätigung an und ruf Lieferant A an, damit er die Schrauben dort storniert.

