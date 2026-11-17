---
title: Planungsausnahmen
summary: Was der Reiter Ausnahmen auflistet, wie du eine Zeile liest, warum jede Art erscheint und wann sie wieder verschwindet.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_lot/get_planning_exceptions.py
  - backend/src/modules/fulfillment/domain/value_objects/planning_exception_kind.py
  - frontend/src/features/production/exceptions/components/PlanningExceptionsTable.vue
  - backend/src/modules/fulfillment/application/use_cases/production_lot/notifications.py
lastVerified: 2026-11-10
---

Der Reiter **Ausnahmen** unter Produktion listet, was eine Planungsentscheidung braucht: Bedarfe, die wieder zu wenig gedeckt sind, Lose mit Fehlmenge, Lose, deren Rohmaterial nicht gesichert ist, und verspätete Lose. Jede Zeile nennt das Problem und verlinkt auf das, was es verursacht hat, die Liste selbst behebt aber nichts. Die Leiste **Planungsausnahmen** über der Liste zeigt, wie viele Ausnahmen es gibt, mit einem Tag je Art. Die Zeilen sind nach Art sortiert, in der Reihenfolge des nächsten Abschnitts, und innerhalb einer Art kommt der früheste Zieltermin oder die älteste Ursache zuerst. Die Liste aktualisiert sich von selbst, und eine Zeile verschwindet, sobald ihre Ursache behoben ist, zum Beispiel wenn der offene Rest wieder zugeteilt oder der Bedarf erfüllt oder abgebrochen ist.

## Was dort erscheint {#kinds}

**Beim Wareneingang verloren** und **Restmenge ausgebucht**: Ein Zukaufteile- oder Rohmaterialbedarf hat einen Teil seiner Menge wieder offen, weil Teile auf seiner Bestellposition beim Wareneingang verloren gingen oder die Restmenge ausgebucht wurde. Teile den Rest einer anderen Position zu, bestell ihn neu oder markiere den Bedarf als erfüllt.

**Los mit Fehlmenge beendet**: Ein Los wurde unter dem zwangsweise abgeschlossen, was ein Fertigungsteile-Bedarf brauchte. Alle mit **Fertigungslose verwalten** bekommen dabei auch eine Benachrichtigung. Leg für den Rest ein neues Los an oder kläre den Bedarf.

**Material fehlt**: Ein Los, das teilweise geplant, geplant, in Bearbeitung oder pausiert ist, nie ein Entwurf, dessen Rohmaterial teilweise weder bestellt noch aus dem Lager genommen ist oder auf einer Position ohne Liefertermin bestellt ist. Sein erster interner Schritt lässt sich erst vollständig einplanen, wenn das Material gedeckt und terminiert ist. Die Zeile fällt weg, sobald der erste Schritt alle seine Stück fertig hat. Ein Los ohne Materialquelle erscheint hier nicht, weil es bewusst auf seine Quelle wartet.

**Verspätet**: Ein Los in denselben Status, dessen Zieltermin überschritten ist oder dessen Fertigungsaufträge erst danach enden sollen.

## Eine Zeile lesen {#row}

**Projekt** zeigt die Projektnummer, die das Projekt öffnet, und darunter den Kunden.

Werden Bilder gespeichert, folgt ein Bild des Artikels. **Artikel** zeigt die Teilenummer eines Fertigungsteils, den Bestellcode eines Zukaufteils oder die Abmessung eines Rohmaterials, darunter den Artikelnamen oder das Material. Klick auf die erste Zeile, um den Artikel zu öffnen. Ein Rohmaterial ohne Abmessung zeigt dort stattdessen sein Material, und ein Fertigungsteil ohne Teilenummer zeigt **Keine Teilenummer** mit einem Warnsymbol.

**Los, Bestellposition, Bedarf** nennt, wo das Problem entstanden ist. Die Losnummer öffnet das Los, die Bestellposition öffnet ihre Bestellung, und die Bedarfsnummer sagt dir, welcher Bedarf zu wenig gedeckt ist.

**Details** sagt in einem Satz, was offen ist oder wie spät das Los dran ist, und **Seit** sagt, wann die Ursache erfasst wurde. Verspätete Lose zeigen dort kein Datum, weil ihr Verzug in den Details steht.

## Beispiele {#examples}

Ein Los zeigt **Material fehlt** mit dem Detail, dass 2 Stk Rohmaterial weder bestellt noch aus dem Lager genommen sind. Öffne das Los und bestell die 2 Stk oder nimm sie aus dem Lager. Die Zeile verschwindet, sobald sie gedeckt ist.

Ein Los zeigt **Verspätet** mit dem Ziel 22. Oktober und dem geplanten Ende 11. November. Öffne das Los und verschieb entweder seinen Zieltermin oder plan seine Fertigungsaufträge so um, dass sie rechtzeitig enden.

## Grenzen {#limits}

Positionen mit verlorenen Teilen oder ausgebuchter Restmenge werden aus den letzten 500 gelesen, zwangsweise abgeschlossene Lose aus den letzten 90 Tagen.
