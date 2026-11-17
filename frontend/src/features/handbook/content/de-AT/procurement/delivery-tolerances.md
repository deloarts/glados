---
title: Liefertoleranzen
summary: Wie weit eine Lieferantenlieferung über oder unter der bestellten Menge liegen darf, wo die Toleranzen eingestellt werden und was in jedem Fall mit der Position passiert.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/delivery_tolerance.py
  - backend/src/modules/fulfillment/application/services/delivery_tolerances.py
  - backend/src/modules/fulfillment/application/use_cases/order/process_order_item_delivery.py
  - backend/src/modules/fulfillment/domain/services/delivery_booking_rules.py
lastVerified: 2026-11-10
---

Lieferanten liefern selten genau die bestellte Menge, deshalb darf eine Position etwas über oder unter ihrer Menge geliefert werden. Die Toleranzen sagen, wie weit, in Prozent der bestellten Menge der Position. Beide stehen anfangs auf 0, dann wird genau die bestellte Menge angenommen und eine Position bleibt offen, bis sie vollständig geliefert ist.

## Wo die Toleranzen eingestellt werden {#settings}

Das globale Paar findest du unter **Einstellungen**, im Reiter **Produktion** der **Systemeinstellungen**, im Abschnitt **Lieferungen**, als **Toleranz für Überlieferung** und **Toleranz für Unterlieferung**. Zum Ändern brauchst du **Einstellungen schreiben**.

Ein Zukaufteil oder ein Rohblock kann in seinem Bearbeitungsformular ein eigenes Paar unter denselben Namen haben. Ein leeres Feld zeigt **Wie in den Einstellungen** und nimmt den globalen Wert, ein eingetragener Wert ersetzt den globalen nur für diesen Artikel. Eine virtuelle Position hat keinen Katalogartikel und nimmt immer die globalen Werte. Eine Position für ein Fertigungsteil beim Lieferanten hat keine Toleranz, weil sie die gezählten Teile ihres Loses trägt.

## Überlieferung {#over}

Innerhalb der Toleranz für Überlieferung kannst du mehr buchen, als die Position noch erwartet, und der Lieferdialog zeigt dir, um wie viel. Die zusätzlichen Teile sind an der Position geliefert und können einem anderen Bedarf zugeordnet werden. Eine Buchung über der Toleranz wird abgelehnt, und die Meldung nennt, wie viel die Position noch annimmt. Bei Stück, Sätzen und anderen gezählten Einheiten wird die Toleranz auf ganze Stück abgerundet, sie lässt also nie einen Bruchteil eines Stücks zu.

## Unterlieferung {#under}

Die Buchung, die die Position innerhalb der Toleranz für Unterlieferung an ihre Menge bringt, bucht ihre Restmenge aus, genau wie **Restmenge ausbuchen**. Die Menge der Position wird zu dem, was sie erhalten hat, ihre Zuordnungen werden an das Eingetroffene angepasst, und die fehlenden Teile bleiben am Bedarf offen, wo du sie neu bestellen oder aus dem Lager nehmen kannst. Eine Buchung, die Teile zur Nachlieferung zurückschickt, lässt die Position offen, weil noch etwas kommt. Eine so ausgebuchte Position kannst du mit **Position wieder öffnen** wieder öffnen, siehe [Aktionen an Bestellpositionen](/handbook/procurement/order-line-actions#close-short).

## Beispiele

**Überlieferung innerhalb der Toleranz.** Bestellt 100, Toleranz 5 %, der Lieferant schickt 103. Buch 103, und der Dialog weist auf 3 mehr hin, als die Position erwartet. Die Position ist mit 103 geliefert, und die 3 zusätzlichen Teile kannst du einem anderen Bedarf zuordnen.

**Unterlieferung innerhalb der Toleranz.** Bestellt 100, Toleranz 2 %, der Lieferant schickt 98 und nichts mehr. Buch 98. Die Restmenge der Position wird bei 98 ausgebucht, und die 2 fehlenden Teile bleiben an ihrem Bedarf offen.

**Zu viel für die Toleranz.** Bestellt 10 Stück, Toleranz 5 %. Das ergibt ein halbes Stück, abgerundet also nichts, deshalb wird eine Buchung von 11 abgelehnt. Buch 10 und schick das zusätzliche Stück zurück, oder erhöh vorher die eigene Toleranz des Artikels.

**Ein Artikel mit eigener Toleranz.** Kabel wird in Metern bestellt, und der Lieferant schneidet immer etwas länger ab. Du setzt beim Kabel **Toleranz für Überlieferung** auf 10, während die Einstellungen bei 0 bleiben. Seine Positionen nehmen bis zu 10 % mehr an, und jeder andere Artikel nimmt weiterhin genau die bestellte Menge.
