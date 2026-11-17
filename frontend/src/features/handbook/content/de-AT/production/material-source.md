---
title: Materialquelle
summary: Wie das Rohmaterial eines Loses gewählt, für ein oder viele Lose geändert, nach der Bestellung gewechselt und vor dem Bedarf freigegeben oder abgelehnt wird.
sourceRefs:
  - frontend/src/features/production/lots/components/LotMaterialSourceDialog.vue
  - frontend/src/features/production/lots/components/LotsListManageSourcePanel.vue
  - frontend/src/features/production/lots/components/LotRejectSourceDialog.vue
  - backend/src/modules/fulfillment/application/use_cases/production_lot/switch_lot_material_source.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/approve_lot_source.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/reject_lot_source.py
lastVerified: 2026-11-10
---

Die Materialquelle eines Loses ist das, woraus sein erster interner Schritt gefertigt wird: ein Rohblock, ein Kaufteil oder ein bestehendes Fertigungsteil, das nachgearbeitet wird. Ein neues Los übernimmt die Quelle seines Fertigungsteils. Ein Rohblock oder Kaufteil gibt dem Los einen Rohmaterialbedarf, den der Einkauf unter **Rohblock Bedarf** deckt, siehe [Lebenszyklus eines Ausgangsartikel-Bedarfs](/handbook/procurement/source-item-demand-lifecycle). Ein nachgearbeitetes Fertigungsteil bekommt keinen Bedarf. Solange ein Los keine Quelle hat, oder keine freigegebene, wo eine Freigabe verlangt ist, wird sein erster interner Schritt nicht eingeplant.

## Die Quelle eines Loses ändern {#change}

Klick auf der Seite des Loses auf **Verwalten** und **Materialquelle ändern**, oder klick ein Los in der Tabelle mit der rechten Maustaste an und wähl **Rohblock hinzufügen**. Der Dialog **Materialquelle ändern** bietet **Rohblock**, **Rohblock erstellen**, **Kaufteil** und **Fertigungsteil** und speichert mit **Anwenden** oder **Erstellen und anwenden**. **Rohblock bestellen** legt den Rohmaterialbedarf von Hand an, wenn ein Los eine Quelle, aber keinen Bedarf hat. Die Quelle zu ändern braucht **Fertigungslose schreiben**, und ohne sie ist die Schaltfläche deaktiviert und zeigt einen Tooltip.

## Viele Lose auf einmal ändern {#batch}

**Quelle verwalten** auf dem Reiter Lose öffnet einen Bereich. Wähl die Lose in der Tabelle aus, wähl das **Ausgangsmaterial** und klick auf **Quelle anwenden**. Abgeschlossene Lose und Lose, deren Material schon ganz eingetroffen ist, werden übersprungen und gezählt. Lose, die schon einen Bedarf haben, werden vorher in einer Frage aufgelistet.

## Wenn das Material schon bestellt ist {#ordered}

Ein offener Bedarf, an dem noch niemand gearbeitet hat, wird storniert und ersetzt, nachdem **Rohblock-Bedarf ersetzen** dich gefragt hat. Ist der Bedarf schon zugeteilt oder bestellt, zeigt **Bestelltes Material wechseln**, wie viel zugeteilt und wie viel eingetroffen ist. Was eingetroffen ist, bleibt beim Los, und der alte Bedarf wird damit abgeschlossen. Zuteilungen auf Bestellpositionen, deren Stück noch nicht eingetroffen sind, werden freigegeben, damit der Einkauf diese Positionen stornieren oder mit Restmenge abschließen kann, und die neue Quelle bekommt einen Bedarf für den fehlenden Rest. Ist das ganze Rohmaterial eingetroffen oder das Los abgeschlossen, lässt sich die Quelle nicht mehr ändern.

## Eine Quelle freigeben {#approval}

Ist **Freigabe für Rohblöcke erforderlich** unter Systemeinstellungen, Produktion eingeschaltet, bekommt ein Los mit einem Rohblock als Quelle erst nach der Freigabe einen Bedarf. Es zeigt **Freigabe erforderlich**, und der Filter **Freigabe erforderlich** listet diese Lose. **Freigeben** und **Ablehnen** findest du auf dem Reiter **Material & Bedarf** des Loses und in der Lostabelle. Beide brauchen **Fertigungslose verwalten** und sind ohne diese Berechtigung deaktiviert, mit einem Tooltip. Die Freigabe legt den Bedarf an, und nach dem Wechsel weg von bestelltem Material deckt er nur den fehlenden Rest, wie es der Wechsel ohne Freigabe täte. Beim Ablehnen gibst du einen **Grund** an, und das Los bleibt **Abgelehnt**, bis jemand es doch freigibt oder die Quelle gewechselt wird. Ein Wechsel startet eine neue Freigabe für die neue Quelle. Kaufteile brauchen nie eine Freigabe. Schaltest du die Einstellung aus, werden die wartenden Lose freigegeben, abgelehnte bleiben aber abgelehnt.

**Freigegebenes Material dem Artikel zuweisen** schreibt den freigegebenen Rohblock zusätzlich in das Fertigungsteil des Loses, sodass künftige Lose damit beginnen. Ein Artikel, der schon einen anderen Rohblock nennt, wird nur geändert, wenn **Bestehendes bei Freigabe überschreiben** eingeschaltet ist, und ein Kaufteil wird nie ersetzt.

## Beispiele

Ein Los mit 20 Haltern hat einen Rohblock als Quelle, und eine Freigabe ist verlangt. Eine Planerin klickt auf **Freigeben**, und für den Einkauf erscheint ein Bedarf über 20 Stk.

20 Stk aus dem falschen Stahl wurden bestellt, 8 sind eingetroffen. Wechsle die Quelle: Die 8 bleiben beim Los, die neue Quelle bekommt einen Bedarf über 12, und der Einkauf klärt die alte Position mit dem Lieferanten.

Eine Quelle wird abgelehnt, weil die Legierung falsch ist. Der Planer wählt einen anderen Rohblock, und das Los wartet wieder auf die Freigabe.
