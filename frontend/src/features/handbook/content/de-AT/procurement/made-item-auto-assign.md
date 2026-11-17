---
title: Lose automatisch zuweisen
summary: Wie Automatisch zuweisen aus jedem Fertigungsteile-Bedarf, dem noch Deckung fehlt, Lose macht, eines pro Projekt und Artikel, und wie Lose verwalten dasselbe für die Bedarfe tut, die du auswählst.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_lot/auto_assign_lots.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/create_lot.py
  - frontend/src/features/production/made-item-demands/components/MadeItemsAutoAssignLotsDialog.vue
  - frontend/src/features/production/made-item-demands/components/MadeItemsDemandsManageLots.vue
lastVerified: 2026-11-10
---

Ein Fertigungsteile-Bedarf wird von einem Fertigungslos gedeckt, und das Anlegen des Loses ist die Zuteilung des Bedarfs. **Automatisch zuweisen** in der Liste **Fertigungsteile Bedarf** macht das für alle Bedarfe auf einmal, **Lose verwalten** für die Bedarfe, die du auswählst. Beide Schaltflächen erscheinen nur, wenn die Fertigungsplanung eingeschaltet ist, und beide brauchen **Fertigungslose schreiben**; ohne die Berechtigung sind sie ausgegraut. Was ein Los danach durchläuft, steht unter [Lebenszyklus eines Loses](/handbook/production/lot-lifecycle).

## Was Automatisch zuweisen vorschlägt

**Automatisch zuweisen** öffnet **Lose automatisch zuweisen** mit einer Vorschau und ändert noch nichts. Es nimmt jeden Fertigungsteile-Bedarf, der Offen oder Zugeteilt ist und noch einen ungedeckten Rest hat, und gruppiert die Bedarfe nach Projekt und Artikel. Jede Gruppe wird ein Los. Die **Losmenge** ist die Summe der Reste, ein Los passt also eins zu eins zu seinen Bedarfen, und **Liefertermin** ist der früheste gewünschte Liefertermin unter ihnen. Eine Gruppe mit einem Bedarf hoher Priorität ist mit **Hoch** markiert, und eine Gruppe aus mehreren Bedarfen listet sie unter **Beitragende Bedarfe**. Bedarfe eines Projekts, das nicht aktiv ist, und eines Artikels, für den kein neuer Bedarf mehr angelegt werden kann, bleiben draußen. Ist nichts mehr zu decken, meldet der Dialog „Kein nicht zugeordneter Bedarf vorhanden." **Lose erstellen** legt alle Lose der Vorschau gemeinsam an.

## Die Bedarfe selbst auswählen

**Lose verwalten** öffnet einen Bereich neben der Tabelle. Wähle Bedarfe in der Tabelle aus, und der Bereich gruppiert sie wie die Vorschau nach Projekt und Artikel. Du kannst Menge, Priorität und gewünschtes Lieferdatum eines Loses ändern, mit **Priorität überschreiben (alle)** oder **Gewünschtes Lieferdatum überschreiben (alle)** jede Zeile setzen und einen Bedarf mit **Aus Gruppe entfernen** herausnehmen. Eine größere Losmenge lässt die zusätzlichen Teile unzugeteilt, eine kleinere gibt den späteren Bedarfen weniger. **Lose erstellen** legt die gezeigten Lose an.

## Beispiele

**Der Normalfall.** Projekt 24017 hat zwei offene Bedarfe für denselben Halter, 8 und 4 Stück. Die Vorschau zeigt ein Los über 12 mit beiden unter **Beitragende Bedarfe**.

**Zwei Projekte.** Derselbe Halter wird auch von Projekt 24020 gebraucht. Er bekommt ein eigenes Los, denn Lose mischen nie Projekte.

**Ein Ersatzstück.** Unter **Lose verwalten** erhöhst du das Los über 12 auf 13. Beide Bedarfe behalten ihre Teile, und das dreizehnte wird als Reserve gefertigt.
