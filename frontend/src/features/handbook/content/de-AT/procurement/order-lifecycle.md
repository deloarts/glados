---
title: Lebenszyklus einer Bestellung
summary: Wie sich der Status einer Lieferantenbestellung und jeder ihrer Positionen aus Angefragtem, Bestelltem, Geliefertem und Storniertem ergibt, und wer eine Position in welchem Status ändern darf.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/order.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/order_item.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/domain/services/order_rules.py
  - backend/src/modules/fulfillment/application/use_cases/order/update_order.py
  - backend/src/modules/fulfillment/application/use_cases/order/update_order_item.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

Eine Lieferantenbestellung und jede ihrer Positionen zeigen einen Status, den die App aus dem ableitet, was du erfasst hast: was angefragt, bestellt, geliefert und storniert wurde. Du setzt ihn nie direkt. Du fragst an, bestellst, buchst Lieferungen, buchst Restmengen aus oder stornierst, und der Status folgt. Was jede dieser Aktionen bewirkt, steht in [Aktionen an Bestellpositionen](/handbook/procurement/order-line-actions).

<StateMachineEmbed machine-key="order_status" />

## Wie sich der Status der Bestellung ergibt

Eine stornierte Bestellung ist **Abgebrochen**, ebenso eine Bestellung, deren Positionen alle storniert sind. Sonst zählen stornierte Positionen nicht: Eine Bestellung mit einer stornierten und einer gelieferten Position ist **Geliefert**. Sobald auf einer nicht stornierten Position etwas eingetroffen ist, steht die Bestellung auf **Teillieferung**, bis jede dieser Positionen geliefert ist.

Eine Bestellung, deren Positionen alle als bestellt markiert wurden, ist **Bestellt**, und sie bleibt bestellt, wenn du später eine Position hinzufügst. Eine Bestellung, bei der manche Positionen bestellt sind und andere noch ausstehen oder angefragt sind, ist **Teilweise bestellt**. Sie gilt als abgesendet, Stornieren braucht also **Bestellungen verwalten**, aber du kannst ihr weiter Positionen hinzufügen, auch aus der [Vergabe einer Angebotsanfrage](/handbook/procurement/quotes#award), und ihre übrigen Positionen bestellen. Eine Korrektur, die jedes gelieferte Stück zurücknimmt, lässt sie auf teilweise bestellt statt auf Entwurf. **Angefragt** und **Entwurf** kommen davor.

## Die Positionen

<StateMachineEmbed machine-key="order_item_status" />

Eine Position beginnt **Ausstehend**, wird **Angefragt** und **Bestellt** und dann **Teillieferung** und **Geliefert**, während Ware eintrifft, siehe [Eine Bestellposition als geliefert markieren](/handbook/procurement/order-item-delivery). Geliefert zählt die angenommenen Teile plus die als verloren abgeschriebenen. Irrtümlich angenommene Teile nimmst du mit einer [Korrektur](/handbook/procurement/delivery-correction) zurück.

## Wer was ändern darf {#permissions}

Eine Bestellung anzulegen und eine Bestellung im Entwurf oder in der Anfrage zu ändern, braucht **Bestellungen schreiben**. Sobald der Lieferant etwas hat, brauchen Änderungen zusätzlich **Bestellungen verwalten**: Das gilt für eine bestellte oder gelieferte Position und für jede Position, sobald die Bestellung bestellt oder geliefert ist. Bei einer teilweise bestellten Bestellung bleiben die ausstehenden und angefragten Positionen für alle mit **Bestellungen schreiben** offen, damit der Einkauf sie fertig bestellen kann. Eine Aktion, die deine Berechtigungen nicht erlauben, erscheint deaktiviert, und ihr Tooltip nennt die fehlende Berechtigung.

Eine stornierte Position nimmt keine Änderungen mehr an, und eine Bestellung, die jemand storniert hat, behält ihre Kopfdaten und nimmt keine neue Position an. Bei einer Position, auf der schon Ware eingetroffen ist, bleiben Artikel, Einheit und Projekt so, wie die Ware gekommen ist. Änderst du den Lieferanten der Bestellung, ziehen die Positionen mit, die den alten Lieferanten genannt haben. Sobald eine Position bestellt ist, liegt sie schon bei diesem Lieferanten, und der Lieferant lässt sich nicht mehr ändern. Ein Liefertermin für alle Positionen erreicht nur die Positionen, die noch auf Ware warten.

## Beispiele

**Eine Position storniert.** Eine Bestellung hat zwei Positionen. Position A kommt vollständig, Position B wird storniert, weil der Artikel nicht mehr gebraucht wird. Die Bestellung ist geliefert.

**Der Lieferant liefert weniger.** Bestellt 10, 8 kommen an, und der Lieferant sagt, die letzten 2 kommen nicht. **Restmenge ausbuchen** bei der Position liefert sie mit 8, und der Bedarf, den sie gedeckt hat, zeigt 2 fehlende Teile, siehe [Restmenge ausbuchen](/handbook/procurement/order-line-actions#close-short).

**Eine teilweise bestellte Bestellung fertig bestellen.** Du markierst Position A nach einem Telefonat als bestellt, Position B steht noch aus. Die Bestellung ist teilweise bestellt. Eine Kollegin, die nur **Bestellungen schreiben** hat, kann Position B trotzdem als bestellt markieren, und die Bestellung ist dann bestellt.
