---
title: Eine Bestellposition als geliefert markieren
summary: Was gelieferte und zurückgewiesene Menge, Lagerort und Materialangaben beim Wareneingang bedeuten und wie es mit einem zurückgewiesenen Teil weitergeht.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/order/process_order_item_delivery.py
  - backend/src/modules/fulfillment/application/use_cases/order/deliver_all_order_items.py
  - backend/src/modules/fulfillment/application/use_cases/order/_made_line_delivery.py
  - backend/src/modules/fulfillment/domain/services/delivery_booking_rules.py
  - backend/src/modules/fulfillment/domain/value_objects/material_receipt.py
  - backend/src/modules/fulfillment/domain/services/order_rules.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
lastVerified: 2026-11-13
---

Der Dialog **Als geliefert markieren** bucht einen Wareneingang für eine Bestellposition. Eine Position mit mehreren Teillieferungen buchst du einmal je Lieferung. Die Position gilt als geliefert, sobald die angenommenen Teile plus die als verloren abgeschriebenen Teile die bestellte Menge erreichen. Zum Buchen brauchst du **Lieferungen erfassen**, ohne diese Berechtigung bleibt die Aktion deaktiviert.

Nur eine bestellte oder teilweise gelieferte Position einer nicht stornierten Bestellung nimmt eine Lieferung an, und eine Position für ein Los nur, solange das Los nicht storniert ist. **Alle als geliefert markieren** bucht alle solchen Positionen gemeinsam, oder keine, wenn eine scheitert, auch auf einer teilweise bestellten Bestellung. Es sagt dir, wie viele Positionen es ausgelassen hat.

## Die zwei Mengenfelder

**Gelieferte Menge** ist die Anzahl der Teile, die du mit dieser Buchung ins Lager übernimmst. Sie ist mit der noch offenen Menge vorbelegt, bei einer vollständigen, unbeschädigten Lieferung bestätigst du also nur. Hat der Lieferant weniger geschickt, setz die Zahl herunter, und die Position bleibt teilweise geliefert und wartet auf den Rest.

**Zurückgewiesene Menge** steht im Block **Stück zurückweisen** und bleibt auf null, solange du ihn nicht aufklappst. Sie zählt die Teile, die du nicht annimmst, weil sie beschädigt, falsch oder außerhalb der Spezifikation sind.

Beide Zahlen zusammen dürfen die noch offene Menge der Position nicht überschreiten, außer die Toleranz für Überlieferung der Position erlaubt mehr, siehe [Liefertoleranzen](/handbook/procurement/delivery-tolerances). Bei einer Position für ein Los müssen die angenommenen Teile außerdem zu dem passen, was der vorige Schritt des Loses bereitgestellt hat.

## Lagerort und Materialangaben {#material}

**Lagerort** ist optional. Er sagt, wohin die Ware gekommen ist, etwa in ein Regal. Bleibt er leer, behält die Buchung den bisherigen Lagerort der Position.

Der Block **Charge, Lieferschein und Zeugnis** ist ebenfalls optional und enthält **Charge oder Schmelze**, **Lieferschein** und **Zeugnis (EN 10204 3.1)**, jeweils bis zu 100 Zeichen. Sie bleiben bei der Lieferung, damit sich Rohmaterial bis zu dem Los zurückverfolgen lässt, das es verbraucht. **Alle als geliefert markieren** fragt einen **Lieferschein** ab und hält ihn bei jeder Position fest, die es bucht.

## Schaden am Lieferschein vermerkt {#damage-noted}

Setz den Haken bei **Schaden am Lieferschein vermerkt**, wenn du den Schaden beim Unterschreiben auf dem Lieferschein des Frächters vermerkt hast, etwa eine eingedrückte Kiste oder eine aufgerissene Palettenfolie. Eine Reklamation beim Frächter hängt meist an diesem Vermerk, deshalb markiert die Lieferhistorie die Buchung mit einem LKW-Symbol. Der Haken weist selbst nichts zurück: Beschädigte Teile buchst du unten als zurückgewiesen, und zeigt sich der Schaden erst beim Auspacken, weist du sie danach zurück, siehe [Eine Lieferung korrigieren](/handbook/procurement/delivery-correction#damage). **Alle als geliefert markieren** hat denselben Haken für die ganze Lieferung.

## Grund und weitere Behandlung

Jedes zurückgewiesene Teil braucht einen **Grund** und eine **Weitere Behandlung**.

**Lieferant liefert nach** heißt, das Teil ist weiterhin offen. Die Position behält ihre bestellte Menge und bleibt teilweise geliefert. Der erwartete Liefertermin wird gelöscht, bis du den Termin einträgst, den der Lieferant bestätigt.

**Stück ist verloren** heißt, das Teil kommt nicht mehr. Es zählt zum Abschluss der Position, die Position kann also ohne dieses Teil geliefert erreichen. Bei einer Zukaufteil- oder Rohmaterial-Position schrumpfen die zugeordneten Bedarfe auf das, was die Position noch bringen kann, und das fehlende Teil erscheint beim neuesten Bedarf wieder. Bei einem Teil eines Loses wird das Los um diese Menge gekürzt, der Verlust erscheint als Ausschuss am Los, und ein Ersatzlos wird angelegt, außer du nimmst den Haken bei **Ersatzlos erstellen** heraus.

## Beispiele

**Vollständige Lieferung.** Bestellt 10, alle 10 kommen unbeschädigt an. Bestätige die vorbelegten 10 und speichere. Die Position ist geliefert.

**Teillieferung.** Bestellt 10, nur 8 kommen an. Setz **Gelieferte Menge** auf 8 und speichere. Die Position zeigt 8 von 10 und bleibt offen. Wenn die letzten 2 kommen, ist der Dialog mit 2 vorbelegt.

**Ein beschädigtes Teil, der Lieferant schickt ein neues.** Bestellt 10, 10 kommen an, eines ist verbeult. Trag 9 geliefert und 1 zurückgewiesen ein, mit dem Grund **Lieferantenschaden** und **Lieferant liefert nach**. Die Position zeigt 9 geliefert und 1 offen.

Zurückweisungen bleiben in der **Lieferhistorie** der Position und speisen das Panel **Zurückweisungen bei Wareneingang je Lieferant** auf der KPI-Seite. Fotos vom Schaden hängst du in der Spalte **Fotos** der Lieferhistorie an die Buchung. Wie du irrtümlich angenommene Teile zurücknimmst oder Teile zurückweist, deren Schaden du erst später findest, steht in [Eine Lieferung korrigieren](/handbook/procurement/delivery-correction).
