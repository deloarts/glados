---
title: Bestellungen verwalten
summary: Wie du Lospositionen an einen Lieferanten übergibst, indem du sie auf eine Bestellung setzt, aus der Losliste oder aus einem einzelnen Los.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_lot/assign_external_position.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/record_lot_position_provision.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - frontend/src/features/production/lots/components/LotsListManageOrdersPanel.vue
lastVerified: 2026-11-10
---

Mit „Bestellungen verwalten“ vergibst du einen Fertigungsschritt nach außen. Du wählst eine Bestellung, klickst die Schritte an, die zu ihrem Lieferanten gehen sollen, über beliebig viele Lose hinweg, und vergibst sie in einem Zug. Jeder Schritt wird eine Position dieser Bestellung, der Lieferant kommt also aus der Bestellung. Was der Schritt danach zeigt, steht unter [Status einer Losposition](/handbook/production/lot-position-lifecycle).

## Das Panel öffnen {#order}

Klick in der Steuerleiste des Tabs Lose auf **Bestellungen verwalten**. Der Button braucht **Fertigungslose schreiben** und **Bestellungen schreiben** und ist ohne diese Berechtigungen deaktiviert, mit einem Tooltip. Wähl die Bestellung unter **Bestellung auswählen**, oder klick auf **Neue Bestellung erstellen**, das den bevorzugten Lieferanten des ersten ausgewählten Schritts vorbefüllt. Der **Smart-Filter** im Menü **Filter** zeigt dann nur Lose, bei denen noch etwas nach außen zu vergeben ist.

Für ein einzelnes Los klickst du auf der Losseite auf **Verwalten** und öffnest dort **Bestellungen verwalten**, oder du klickst bei einer Position auf **Extern vergeben**. Dieses Formular fragt zusätzlich nach **Einheit** und **Stück pro Einheit**. Die Schrittliste bietet einen dritten Weg, beschrieben unter [Produktion verwalten](/handbook/production/manage-production#step-list).

## Welche Schritte du anklicken kannst {#steps}

Du kannst einen Schritt anklicken, dessen Position noch Stück übrig und keine offene Lieferantenposition hat, solange das Los noch aktiv ist. Eine nicht zugewiesene Position wird Extern, eine schon im Haus geplante wird Gemischt. Eine Position, deren Lieferantenposition mit Restmenge ausgebucht wurde, kannst du für den Rest erneut vergeben. Ein Warnsymbol markiert eine Position ohne Schritt, der als üblicherweise extern markiert ist, vergeben kannst du sie trotzdem.

## Was du je Zeile einträgst {#fields}

Jede Zeile zeigt Losnummer, Position, Fertigungsverfahren und offene Stück. **Menge** beginnt bei allen offenen Stück und nimmt ganze Stück von 1 bis zu dieser Zahl. **Preis**, **Erwartete Lieferung** und **Erwartete Abholung** sind optional, und der Preis gilt in der Anzeigewährung. Die Position zählt in Stück, und du kannst sie später auf der Bestellung ändern.

## Vergeben {#assign}

**Position vergeben** funktioniert, sobald eine Bestellung und mindestens ein Schritt ausgewählt sind. Jede Zeile wird für sich vergeben. Erfolgreiche Zeilen verlassen die Auswahl, fehlgeschlagene bleiben ausgewählt, und eine Meldung nennt sie. Das Panel bleibt offen und die Liste wird aktualisiert. Eine Vergabe wird abgelehnt, wenn jemand die Bestellung storniert hat oder das Projekt des Loses nicht aktiv ist.

Solange die Bestellung ein Entwurf oder angefragt ist, reicht **Bestellungen schreiben**, und bei einer teilweise bestellten Bestellung auch, weil die neue Position noch nicht beim Lieferanten liegt. Ist die ganze Bestellung bestellt, brauchst du **Bestellungen verwalten**.

Die neue Position beginnt als ausstehend, daher zeigt der Schritt **Zugeordnet**, bis der Einkauf die Position als bestellt markiert.

## Material an den Lieferanten schicken {#provisions}

Schickst du Teile an den Lieferanten, klick bei einer externen oder gemischten Position auf **Bereitstellung erfassen**, nachdem du auf der Losseite auf **Verwalten** geklickt hast, und trag **Menge**, **Datum** und optional eine **Notiz** ein. Du kannst nicht mehr erfassen, als der vorherige Schritt bereitgestellt hat. Das braucht **Fertigungslose schreiben**.

## Eine Vergabe rückgängig machen {#undo}

Klick bei der Position auf **Vergabe aufheben**, oder lösch die Position aus der Bestellung. Beides geht nur, solange die Position ausstehend oder angefragt ist und keine Bereitstellung erfasst wurde. Die Position fällt auf Intern zurück, wenn hauseigene Arbeit bleibt, sonst auf Nicht zugewiesen.

## Beispiele {#examples}

Du vergibst 30 von 100 Stück eines Frässchritts an einen Lieferanten. Der Schritt zeigt **Zugeordnet**, und die anderen 70 bleiben frei für „Produktion verwalten“.

Du vergibst drei Schritte in einem Zug, und einer schlägt fehl, weil das Projekt seines Loses nicht mehr aktiv ist. Zwei Positionen werden angelegt, und die fehlgeschlagene Zeile bleibt ausgewählt.
