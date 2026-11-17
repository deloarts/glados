---
title: Lebenszyklus eines Fertigungsteile-Bedarfs
summary: Wie der Bedarf eines Projekts an einem Fertigungsteil von offen über Zuteilung und Losplanung bis zur Erfüllung wandert, und was sein Abbrechen mitnimmt.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/demand.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/domain/services/demand_status_rules.py
  - backend/src/modules/fulfillment/application/use_cases/made_item_demand/cancel_demand.py
  - backend/src/modules/fulfillment/application/use_cases/made_item_demand/update_demand_item_status.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

Ein Fertigungsteile-Bedarf ist der Bedarf eines Projekts an einem hauseigen gefertigten Teil, eine Zeile in der Liste **Fertigungsteile Bedarf**. Sein Status folgt denselben Regeln wie ein [Zukaufteile-Bedarf](/handbook/procurement/bought-item-demand-lifecycle), hier wird aber nichts bei einem Lieferanten gekauft: Ein Fertigungslos deckt den Bedarf, und der Fortschritt des Loses zählt als Lieferung. Das Diagramm unten wird live aus den Regeln gelesen, nach denen das System arbeitet.

<StateMachineEmbed machine-key="made_item_demand_status" />

## Was jeder Status bedeutet

**Offen** hat nichts zugeteilt. **Zugeteilt** heißt, es ist etwas zugeteilt, aus dem Lager oder von einem Los, aber der Bedarf ist noch nicht vollständig gedeckt und platziert, der Rest bleibt also für **Automatisch zuweisen** sichtbar, siehe [Lose automatisch zuweisen](/handbook/procurement/made-item-auto-assign). **Bestellt** heißt, Zuteilungen und Lager decken die ganze Menge, und jedes Los dahinter hat im [Lebenszyklus eines Loses](/handbook/production/lot-lifecycle) **Entwurf** verlassen und ist weder storniert noch verschrottet. Ein pausiertes Los zählt auch, denn das Planen des Loses ist die Zusage. **Erfüllt** ist erreicht, sobald die von seinen Losen fertiggestellten Teile plus Lager die Menge decken, was das Lager allein in einem Schritt aus Offen schaffen kann, oder wenn jemand den Bedarf von Hand als erfüllt markiert. **Abgebrochen** ist das andere Ende. Ein Bedarf geht auch zurück, wenn sich auflöst, was ihn deckt, zum Beispiel wenn ein Los storniert oder eine Zuteilung entfernt wird.

## Wie fertige Teile verteilt werden

Deckt ein Los mehrere Bedarfe, gehen die fertigen Teile in einer festen Reihenfolge an sie, der älteste Bedarf zuerst. Der erste Bedarf ist also erfüllt, sobald seine eigenen Teile fertig sind, der nächste wartet auf die Teile danach. Schrumpft das Los durch Ausschuss oder Nacharbeit, geben die Bedarfe in umgekehrter Reihenfolge Teile ab, beginnend beim neuesten, und ein schon erfüllter Bedarf erst nach allen offenen. Die abgegebenen Teile wandern zum Ersatzlos oder Nacharbeitslos, wenn eines angelegt wird.

## Einen Status von Hand setzen

Von Hand setzt du nur zwei Status, **Erfüllt** und **Abgebrochen**, über **Status setzen** im Zeilenmenü oder über die Status-Schaltflächen im Bedarfsdialog. Für beide brauchst du **Bedarfsteile schreiben** und **Bedarfsteile verwalten**; ohne sie sind die Schaltflächen ausgegraut, und der Tooltip nennt die fehlende Berechtigung. Markierst du einen Bedarf als erfüllt, bleiben seine Lose, wie sie sind: Sie fertigen weiter, und ihre Teile bleiben ihm zugeteilt.

Abbrechen zeigt zuerst, was mitgeht: Die nur für diesen Bedarf gebauten Lose werden mit ihren Fertigungsaufträgen, Lieferantenpositionen und Rohmaterialbedarfen storniert, ein Los, das auch anderen Bedarfen gehört, verliert nur den Anteil dieses Bedarfs, und die Lagerzuteilung wird freigegeben. Decken Lose den Bedarf, brauchst du dafür auch **Fertigungslose verwalten**. Ein nur für diesen Bedarf gebautes Los, das schon Gutteile hat, wird nicht storniert, das Abbrechen wird also abgelehnt: Schließ dieses Los zuerst mit **Los abschließen** vorzeitig ab, siehe [Lebenszyklus eines Loses](/handbook/production/lot-lifecycle), und brich den Bedarf danach ab. Ein erfüllter oder abgebrochener Bedarf nimmt keine der beiden Aktionen mehr an und lässt sich nicht mehr bearbeiten. Jede Aktion steht unter [Statusübergänge eines Fertigungsteile-Bedarfs](/handbook/procurement/made-item-demand-transitions).

## Beispiele

**Ein Los für zwei Bedarfe.** Ein Los über 12 Halter deckt Bedarf 201 mit 8 und Bedarf 204 mit 4. Die ersten 8 Gutteile erfüllen Bedarf 201, Bedarf 204 wird mit den letzten 4 erfüllt.

**Abbrechen vor der Fertigung.** Ein Bedarf über 5 Wellen hat ein eigenes geplantes Los, und noch ist nichts gefertigt. Der Dialog **Bedarf stornieren** zeigt das Los und seine Fertigungsaufträge als storniert, und du bestätigst.

**Ein abgelehntes Abbrechen.** Dasselbe Los hat schon 2 gute Wellen fertig. Das Abbrechen wird abgelehnt, also schließt du das Los bei 2 ab und brichst den Bedarf danach ab.
