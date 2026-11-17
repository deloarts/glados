---
title: Lebenszyklus eines Zukaufteile-Bedarfs
summary: Wie der Bedarf eines Projekts an einem Zukaufteil von offen über Zuteilung und Bestellung bis zur Erfüllung wandert, und welche zwei Status du von Hand setzt.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/demand.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/domain/services/demand_status_rules.py
  - backend/src/modules/fulfillment/application/use_cases/_demand_family/update_status.py
  - backend/src/modules/fulfillment/application/use_cases/bought_item_demand/cancel_demand_item.py
  - frontend/src/features/procurement/utils/demandDisplayStatus.ts
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

Ein Zukaufteile-Bedarf ist der Bedarf eines Projekts an einem gekauften Teil, eine Zeile in der Liste **Zukaufteile Bedarf**, unabhängig von einer einzelnen Bestellung geführt. Sein Status ergibt sich aus seinen Zuteilungen und den Bestellpositionen dahinter, jedes Mal, wenn sich eines davon ändert. Das Diagramm unten wird live aus den Regeln gelesen, nach denen das System arbeitet.

<StateMachineEmbed machine-key="bought_item_demand_status" />

## Was jeder Status bedeutet

**Offen** hat nichts zugeteilt. **Zugeteilt** heißt, es ist etwas zugeteilt, aus dem Lager oder von einer Bestellposition, aber der Bedarf ist noch nicht vollständig gedeckt und platziert, der Rest bleibt also für **Auto-Zuteilen** sichtbar. **Bestellt** heißt, Zuteilungen und Lager decken die ganze Menge, und jede Bestellposition dahinter ist bestellt oder schon weiter. **Erfüllt** ist erreicht, sobald die gelieferten Teile plus Lager die Menge decken, was das Lager allein in einem Schritt aus Offen schaffen kann, oder wenn jemand den Bedarf von Hand als erfüllt markiert. **Abgebrochen** ist das andere Ende. Ein Bedarf geht auch zurück, wenn sich auflöst, was ihn deckt, zum Beispiel wenn eine Bestellposition storniert oder eine Zuteilung entfernt wird.

Die Tabelle zeigt denselben Status in feineren Stufen. **Teilweise zugeteilt** und **Teilweise bestellt** markieren einen Bedarf, der erst teilweise gedeckt oder bestellt ist, und **Teilweise geliefert** einen, dessen erste Teile eingetroffen sind. Wie du einen Bedarf aus Bestellungen und aus dem Lager deckst, steht unter [Bedarfe zuteilen](/handbook/procurement/demand-allocations).

## Wie eintreffende Teile verteilt werden

Deckt eine Bestellposition mehrere Bedarfe, gehen die eintreffenden Teile in einer festen Reihenfolge an sie: zuerst die Zukaufteile-Bedarfe, dann die Rohmaterialbedarfe, jeweils der älteste Bedarf zuerst. Der erste Bedarf ist erfüllt, sobald seine eigenen Teile da sind, der nächste wartet auf die Teile danach. Es zählen nur angenommene Teile. Ein als verloren ausgebuchtes Teil trifft nie ein, deshalb schrumpfen die Zuteilungen der Position auf das, was sie noch bringen kann, beginnend beim neuesten Bedarf, und die fehlenden Teile erscheinen bei diesem Bedarf wieder als Zugeteilt oder Offen.

## Einen Status von Hand setzen

Von Hand setzt du nur zwei Status, **Erfüllt** und **Abgebrochen**, über **Status setzen** im Zeilenmenü oder über die Status-Schaltflächen im Bedarfsdialog. Für beide brauchst du **Bedarfsteile schreiben** und **Bedarfsteile verwalten**; ohne sie sind die Schaltflächen ausgegraut, und der Tooltip nennt die fehlende Berechtigung. Abbrechen gibt jede Zuteilung frei, auf Bestellpositionen und aus dem Lager, damit die Kapazität der Position und das Lager wieder frei sind. Wenn du einen Bedarf als erfüllt markierst, fragt Glados vorher nach und behält nur, was für ihn schon eingetroffen ist: Der Teil seiner Zuteilungen auf Bestellpositionen, dessen Teile noch nicht eingetroffen sind, wird freigegeben, damit du diese Positionen verkleinern oder anderen Bedarfen zuteilen kannst. Zuteilungen aus dem Lager bleiben. Ein erfüllter oder abgebrochener Bedarf nimmt keine der beiden Aktionen mehr an und lässt sich nicht mehr bearbeiten. Bis dahin änderst du Notiz, Termine und Markierungen, und die Menge, solange sie nicht unter das schon Zugeteilte fällt. Jede Aktion mit den Status, aus denen sie startet, steht unter [Statusübergänge eines Zukaufteile-Bedarfs](/handbook/procurement/bought-item-demand-transitions).

## Beispiele

**Aus dem Lager gedeckt.** Ein Bedarf über 10 Relais ist Offen, und 10 liegen im Regal. **Aus Lager decken** mit 10 bringt ihn direkt auf Erfüllt.

**Eine Position für zwei Bedarfe.** Eine Bestellposition über 30 deckt Bedarf 101 mit 20 und Bedarf 105 mit 10. Die ersten 20 eintreffenden Teile erfüllen Bedarf 101, Bedarf 105 wartet auf die letzten 10.

**Einen Bedarf früher schließen.** Ein Bedarf über 8 hat 5 geliefert und 3 noch in Bestellung. Du markierst ihn als erfüllt, er behält die 5, und die 3 auf der Position werden für einen anderen Bedarf frei.
