---
title: Angebote verwalten
summary: Wie du Lospositionen, die ein Lieferant bearbeiten könnte, aus der Lostabelle oder von der Seite des Loses auf eine Angebotsanfrage setzt, und was die Vergabe damit macht.
sourceRefs:
  - frontend/src/features/production/lots/components/LotsListManageQuotesPanel.vue
  - frontend/src/features/production/lots/components/LotManageQuotesPanel.vue
  - frontend/src/features/quote-requests/components/QuoteRequestPanel.vue
  - backend/src/modules/fulfillment/application/use_cases/quote_request/_lines.py
  - backend/src/modules/fulfillment/application/use_cases/quote_request/award_quote_request.py
lastVerified: 2026-11-10
---

Geht ein Schritt wie Beschichten oder Härten an einen Lieferanten, willst du vielleicht vor der Bestellung Preise von mehreren Lieferanten. **Angebote verwalten** setzt Lospositionen auf eine Angebotsanfrage statt auf eine Bestellung. Die Lieferanten bieten auf der Anfrage an, und ihre Vergabe setzt später jede Position auf die Bestellung des Lieferanten, der sie gewonnen hat, so wie es [Bestellungen verwalten](/handbook/production/manage-orders) tun würde. Wie eine Angebotsanfrage verschickt, verglichen und vergeben wird, erklärt [Angebote](/handbook/procurement/quotes).

## Aus der Lostabelle {#list}

Klick auf dem Reiter Lose auf **Angebote verwalten**. Das braucht **Fertigungslose schreiben** und **Bestellungen schreiben**, und ohne eine davon ist die Schaltfläche deaktiviert und ihr Tooltip nennt die fehlende. Klick Arbeitsschritte in der Tabelle an, um ihre Positionen in den Bereich zu holen. Jede Zeile nennt Los und Position, Teilenummer und Verfahren und startet mit der Menge, die die Position noch abgeben kann. Du kannst sie verringern, aber nicht darüber erhöhen.

Wähl unter **Angebotsanfrage** eine Anfrage im Entwurf oder eine verschickte, oder leg mit **Neue Angebotsanfrage** eine an, und klick auf **Zur Angebotsanfrage hinzufügen**. Die Positionen werden hinzugefügt und die Auswahl wird geleert. **Auswahl aufheben** leert den Bereich, ohne etwas hinzuzufügen.

## Von der Seite des Loses {#lot}

Klick auf der Seite des Loses auf **Verwalten** und dann über den Positionen auf **Angebote verwalten**. Das braucht **Bestellungen schreiben**. Der Bereich listet jede Position des Loses, die ein Lieferant noch bearbeiten kann, mit ihrer offenen Menge. Nimm eine Zeile, die du nicht anfragen willst, mit **Weglassen** heraus und füg den Rest wie oben hinzu.

## Wie es weitergeht {#award}

Eine Position auf einer offenen Anfrage zeigt in der Lostabelle und auf der Seite des Loses **In Anfrage**. Die Anfrage reserviert nichts, die Position lässt sich also in der Zwischenzeit weiter über Bestellungen verwalten bestellen. Wird die Anfrage vergeben, kommt jede Position auf eine Bestellung im Entwurf oder eine teilweise bestellte ihres Gewinners, mit der angebotenen Menge oder mit dem, was die Position noch abgeben kann, je nachdem, was kleiner ist. Eine Position, die sich nicht mehr zuweisen lässt, weil sie schon auf einer aktiven Bestellposition steht, ihr Los beendet ist oder nichts mehr übrig ist, behält ihre Anfrageposition mit einer Warnung offen.

## Beispiele

Position 3 eines Loses mit 40 Stück soll pulverbeschichtet werden. Öffne die Seite des Loses, klick auf **Verwalten** und **Angebote verwalten**, lass alle anderen Positionen weg, wähl die Anfrage für die Beschichtungen dieses Monats und klick auf **Zur Angebotsanfrage hinzufügen**.

Fünf Lose müssen eloxiert werden. Öffne auf dem Reiter Lose **Angebote verwalten**, klick den Eloxierschritt jedes Loses an, leg mit **Neue Angebotsanfrage** eine neue Anfrage an und füg alle fünf Positionen auf einmal hinzu.

Eine Position wurde über Bestellungen verwalten bestellt, bevor die Anfrage vergeben war. Die Vergabe überspringt sie, und ihre Anfrageposition bleibt mit einer Warnung offen, sodass du sie aus der Anfrage nehmen kannst.
