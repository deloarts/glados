---
title: Art einer Losposition
summary: Der Klassifizierer hinter dem Positions-Badge, nicht zugewiesen, extern, intern oder gemischt, wie er sich aus der zugesagten Arbeit ergibt und warum er keinen Endzustand hat.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/lot_position.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/assign_external_position.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/assign_internal_position.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

Die Art ist das Badge, das neben einer Losposition steht, in der Schrittliste der Losseite, auf ihren Positionskarten und im Verwaltungsmodus, in der WIP-Tabelle und im Wartezeit-Panel der KPIs, und beantwortet eine Frage: Wer erledigt diesen Schritt. Das ist etwas anderes als der Status einer Position, beschrieben unter [Status einer Losposition](/handbook/production/lot-position-lifecycle). Die Art sagt, wer zuständig ist, der Status sagt, wie weit sie schon sind. Die Art ändert auch, wie der Status heißt: Ein ausstehender externer oder gemischter Schritt zeigt **Zugeordnet**, ein bestellter externer **Bestellt**, ein eingeplanter interner **Eingeplant**, und nur ein gemischter **Bestellt / Eingeplant**. Niemand setzt die Art, sie ergibt sich aus der Arbeit, die auf der Position zugesagt ist.

<StateMachineEmbed machine-key="lot_position_kind" />

**Nicht zugewiesen** ist der Startpunkt jeder Position, noch ist nichts zugesagt. Eine aktive Lieferantenbestellposition auf der Position, angelegt über [Bestellungen verwalten](/handbook/production/manage-orders), macht sie **Extern**. Ein aktiver Fertigungsauftrag aus [Produktion verwalten](/handbook/production/manage-production) oder schon im Haus gefertigte Teile machen sie **Intern**, und beide Seiten zusammen machen sie **Gemischt**, ein Teil zugekauft, ein Teil hauseigen gefertigt. Eine stornierte Bestellposition oder ein stornierter Fertigungsauftrag zählt nicht mehr, die Teile, die ein stornierter Fertigungsauftrag vor dem Stornieren gefertigt hat, aber schon. Eine Zusage rückgängig zu machen, geht deshalb denselben Weg zurück: Wird die Bestellposition entfernt oder storniert, fällt die Position auf Intern zurück, wenn hauseigene Arbeit oder Teile bleiben, sonst auf Nicht zugewiesen, und wird die hauseigene Seite storniert, fällt sie auf Extern zurück, solange diese nichts gefertigt hat. Eine Lieferantenposition, deren Restmenge ausgebucht wurde, zählt weiter als aktiv, die Position bleibt also Extern oder Gemischt, und für den Rest kann daneben eine neue Position angelegt werden. Eine Position über 10 Stück mit 4 beim Lieferanten bestellten und 6 auf einer Maschine geplanten ist Gemischt. Stornierst du die Bestellposition, bevor etwas eintrifft, ist sie Intern.

Auffällig: Hier gibt es keinen Endzustand. Die Art ist kein Lebenszyklus mit einem Ende, sondern eine laufende Einstufung, die sich aus dem ergibt, was gerade zugesagt ist. Die Zeilen oben zeigen das in der Reihenfolge, in der das System sie prüft.
