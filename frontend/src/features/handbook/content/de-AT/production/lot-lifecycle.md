---
title: Lebenszyklus eines Loses
summary: Wie sich der Status eines Loses aus seinen Positionen und den Aktionen daran ergibt, und was Pausieren, vorzeitiges Abschließen, Stornieren und Verschrotten bewirken.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/lot.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/lot_lifecycle.py
  - backend/src/modules/fulfillment/application/services/lot_cascades.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/update_lot.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/notifications.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

Der Status eines Loses wird nie direkt gesetzt. Er ergibt sich aus seinen Positionen, beschrieben unter [Status einer Losposition](/handbook/production/lot-position-lifecycle), und aus den Aktionen am Los selbst. Die Tabelle wird live aus den Regeln gelesen, die das System ausführt, und die erste passende Zeile setzt den Status.

<StateMachineEmbed machine-key="lot_status" />

## Wie der Status entsteht {#status}

Ein neues Los startet als **Entwurf** und wandert über **Teilweise geplant** und **Geplant**, während seine Positionen vergeben werden, noch bevor gearbeitet wird. **In Bearbeitung** heißt, es läuft echte Produktion. Ein Los ist **Abgeschlossen**, sobald jede Position abgeschlossen ist. Solange ein Los ein Entwurf ist, kannst du seine Menge ändern, aber nie unter das, was Fertigungsteile-Bedarfe dem Los zugeteilt haben. Eine noch nicht bestellte Lieferantenposition schrumpft mit ihrer Position, und der Rohmaterialbedarf geht anteilig mit. Die Änderung wird abgelehnt, wenn dieser Bedarf schon zugeteilt oder bestellt ist oder die neue Menge keine ganze Zahl gezählter Stück ergibt.

## Ein Los pausieren {#hold}

**Pausieren** wird bei einem Los angeboten, das teilweise geplant, geplant oder in Bearbeitung ist, und fragt nach einem **Grund**. Es hält die laufenden Fertigungsaufträge des Loses an. Solange das Los pausiert ist, lässt sich keiner seiner Aufträge starten oder fortsetzen, und auf ihnen wird keine Fertigmeldung, kein Ausschuss und kein Storno gebucht, Lieferungen und das Bestellen seiner Lieferantenpositionen gehen aber weiter. **Fortsetzen** setzt genau die Aufträge fort, die das Pausieren angehalten hat, ein Auftrag, den du selbst pausiert hast, bleibt pausiert. Ein pausiertes Los wird trotzdem abgeschlossen, wenn seine letzten Teile fertig sind. Beide Aktionen brauchen **Fertigungslose schreiben**.

## Ein Los vorzeitig beenden {#end}

**Los abschließen** schließt ein Los vorzeitig ab, wenn es sich nicht fertigstellen lässt. Dafür braucht irgendeine Position ein Gutteil, und du brauchst **Fertigungslose verwalten**. Das Los schrumpft auf das, was seine letzte Position produziert hat, die Gutteile zwischen den Positionen werden als verworfen festgehalten, jeder Fertigungsauftrag endet bei dem, was er bearbeitet hat, oder wird storniert, wenn er nichts bearbeitet hat, und die Bedarfe des Loses werden entsprechend verringert. Als geliefert gebucht wird nichts, was nicht angekommen ist.

**Los stornieren** beendet das Los und storniert seine offene Arbeit, solange noch keine Position ein Gutteil hat, und braucht ebenfalls **Fertigungslose verwalten**. Ein Los mit Gutteilen schließt du stattdessen mit **Los abschließen** ab. Noch nicht bestellte Lieferantenpositionen werden storniert, eine teilweise gelieferte wird mit Restmenge ausgebucht, und eine bestellte Position ohne Lieferung bleibt offen, damit der Einkauf sie mit dem Lieferanten klären kann. Keine der beiden Aktionen lässt sich rückgängig machen.

## Was mit dem Rohmaterial passiert {#material}

Beide Aktionen rechnen den Rohmaterialbedarf des Loses ab. Wurde davon nichts bestellt oder aus dem Lager genommen, wird er storniert. Sonst gilt er beim Eingetroffenen als erfüllt, und der noch nicht eingetroffene Teil seiner Lieferantenpositionen wird freigegeben. Alle mit **Bestellungen schreiben** bekommen eine Benachrichtigung, und eine Mail, wenn Mail eingerichtet ist, mit den Lieferantenpositionen, die noch zu klären sind.

## Verschrottete Lose {#scrapped}

**Teile verschrotten** nimmt Stück aus einem Schritt, dessen Fertigungsauftrag läuft, mit einem **Grund**. Bei einem pausierten Los wird es nicht angeboten. Standardmäßig legt es ein Neufertigungs-Los für die verschrotteten Stück an. Nimmst du das Häkchen bei **Neufertigungs-Los erstellen** weg, decken einfach weniger Stück die Bedarfe des Loses. Alle mit **Fertigungslose verwalten** werden benachrichtigt. Ein Los, dessen Menge so auf null sinkt, ist **Verschrottet**.

## Materialquelle {#source}

Ein Los, dessen Rohblock eine Freigabe braucht, wartet, bis die Quelle freigegeben ist, und sein Rohmaterialbedarf wird dann angelegt. Freigeben, Ablehnen und Wechseln der Quelle erklärt [Materialquelle](/handbook/production/material-source).
