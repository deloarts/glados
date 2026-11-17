---
title: Status einer Losposition
summary: Wie sich der Status einer Losposition aus ihren Lieferantenpositionen und Fertigungsaufträgen ergibt, und warum derselbe Status bei internen und externen Schritten anders heißt.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/lot_position.py
  - backend/src/modules/fulfillment/domain/services/lot_rules.py
  - frontend/src/features/production/utils/lotStatus.ts
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

Jeder Schritt eines Loses gehört zu einer Position, und der Status der Position ist das, was die Losliste und die Losseite für diesen Schritt zeigen. Niemand setzt ihn. Er ergibt sich aus der Lieferantenposition, angelegt über [Bestellungen verwalten](/handbook/production/manage-orders), und aus den Fertigungsaufträgen, angelegt über [Produktion verwalten](/handbook/production/manage-production). Der Status des Loses ergibt sich dann aus allen seinen Positionen, siehe [Lebenszyklus eines Loses](/handbook/production/lot-lifecycle).

<StateMachineEmbed machine-key="lot_position_status" />

## Wie der Status entsteht {#statuses}

Die Zeilen der Tabelle werden von oben geprüft, und die erste, die zutrifft, setzt den Status. Eine Position eines stornierten Loses ist **Storniert**. Eine Position, deren fertige Stück ihre Menge erreichen, ist **Abgeschlossen**, und eine mit einigen fertigen Stück ist **Teilweise abgeschlossen**. Eine Position mit einem laufenden oder pausierten Fertigungsauftrag ist **In Bearbeitung**. Ein Lieferant meldet keinen Start, daher überspringt eine rein externe Position diesen Status. Eine Position, deren Lieferantenposition bestellt oder teilweise geliefert ist oder die einen eingeplanten Fertigungsauftrag hat, ist bestellt oder eingeplant. Alles andere ist ausstehend.

## Was der Schritt zeigt {#labels}

Die Art der Position entscheidet, wie die letzten beiden Status heißen, denn eine interne Position kann nur eingeplant und eine externe nur bestellt sein. Eine eingeplante interne Position zeigt **Eingeplant**, eine bestellte externe **Bestellt**, und nur eine gemischte zeigt **Bestellt / Eingeplant**. Eine ausstehende externe oder gemischte Position zeigt **Zugeordnet**, weil es eine Lieferantenposition gibt, die der Einkauf noch nicht bestellt hat. Eine ausstehende nicht zugewiesene oder interne Position zeigt **Ausstehend**. Die Art selbst erklärt [Art einer Losposition](/handbook/production/lot-position-kind).

## Nachdem bestellt wurde {#after}

Einen Schritt an einen Lieferanten zu vergeben hält die Absicht fest, die Position als bestellt zu markieren die Zusage. Erst dann wechselt der Schritt auf **Bestellt**, und das Los geht meist auf Teilweise geplant oder Geplant. Jede Lieferung zählt ihre Stück zu den fertigen Stück der Position. Bei einer gemischten Position addieren sich gelieferte und im Haus gefertigte Stück, keine Seite überschreibt die andere. Eine Lieferung kann nicht mehr Stück zählen, als der vorherige Schritt gefertigt hat. Bei einem gemischten ersten Schritt ist der hauseigene Anteil außerdem durch das eingetroffene Rohmaterial begrenzt.

## Eine Position aufteilen {#mixed}

Eine Position kann teils an einen Lieferanten und teils an die Werkstatt gehen. Beide Seiten nehmen aus denselben offenen Stück, eine Position über 100 mit 30 extern bestellten lässt also 70 für „Produktion verwalten“. Ein stornierter Fertigungsauftrag gibt die Stück zurück, die er noch nicht gefertigt hat, und die gefertigten bleiben gezählt. Eine Lieferantenposition gibt nichts zurück, bis sie entfernt oder storniert wird.

## Beispiele {#examples}

Du setzt einen Entgratschritt über 50 Stück auf eine Bestellung im Entwurf. Der Schritt zeigt **Zugeordnet**. Der Einkauf schickt die Bestellung ab und markiert die Position als bestellt, und der Schritt zeigt **Bestellt**. Der Lieferant liefert 20, und der Schritt zeigt **Teilweise abgeschlossen**.

Eine Position über 10 hat 4 Stück auf einer Lieferantenposition und 6 auf einer Maschine eingeplant. Bevor etwas bestellt oder gestartet ist, zeigt sie **Bestellt / Eingeplant**, weil ihr Fertigungsauftrag eingeplant ist.
