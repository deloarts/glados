---
title: Lebenszyklus eines Fertigungsauftrags
summary: Was der Status eines Fertigungsauftrags bedeutet, während er wartet, läuft, pausiert und auf einer Maschine fertig wird, was ein Start braucht und wie eine Fertigmeldung korrigiert wird.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/production_order.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/production_order_lifecycle.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/reverse_production_order_completion.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/split_production_order.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/merge_production_orders.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

Ein Fertigungsauftrag ist ein Eintrag in der Warteschlange einer Maschine, der hauseigene Anteil der Arbeit an einer Losposition, angelegt, wenn [Produktion verwalten](/handbook/production/manage-production) eine Position vergibt. Sein Status steht auf der Warteschlange, auf der Seite der Maschine, in der Schrittliste des Loses, in der WIP-Tabelle und auf der eigenen Seite des Auftrags. Er ergibt sich aus dem, was am Auftrag erfasst wurde: sein Start, seine Pausen und seine Fertigmeldungen.

<StateMachineEmbed machine-key="production_order_status" />

## Status {#statuses}

**Eingeplant** heißt, der Auftrag wartet, bis er dran ist. Der Start macht einen Auftrag **In Bearbeitung** und hält seinen tatsächlichen Start einmal fest, ein späteres Fortsetzen verschiebt ihn also nicht. Ein Auftrag ist **Abgeschlossen**, sobald die auf ihm erfassten Stück seine Menge erreichen. Gutteile und Ausschuss zählen beide, und Ausschuss lässt sich nur auf einer Prüfposition buchen. Ein abgeschlossener Auftrag geht zurück auf **In Bearbeitung**, wenn eine seiner Fertigmeldungen storniert wird.

**Storniert** ist der einzige endgültige Status. Ein Auftrag wird storniert, wenn ihn jemand storniert, wenn sein Los storniert wird, wenn sein Los vorzeitig abgeschlossen wird, bevor der Auftrag etwas bearbeitet hat, wenn sein Bedarf für das Fertigteil abgebrochen wird, wenn er in einen anderen Auftrag zusammengeführt wird, wenn eine Lieferantenlieferung seine Position deckt oder wenn Ausschuss nichts mehr für ihn übrig lässt. Deine eigenen Aufträge stornierst du mit **Fertigungsaufträge schreiben**, die Aufträge anderer mit **Fertigungsaufträge verwalten**.

## Pausen {#pauses}

**Pausiert** gilt genau so lange, wie eine Unterbrechung offen ist, und davon gibt es zwei Arten. Eine Pause, die du selbst am Auftrag setzt, endet, wenn du den Auftrag fortsetzt. Eine Pause, die vom Pausieren des Loses kommt, endet erst, wenn das Los fortgesetzt wird, siehe [Lebenszyklus eines Loses](/handbook/production/lot-lifecycle#hold). Solange das Los pausiert ist, lassen sich seine Aufträge nicht starten oder fortsetzen, und sie nehmen keine Fertigmeldung, keinen Ausschuss und kein Storno an. Pausierte Zeit zählt nicht als Arbeitszeit.

## Starten und Fortsetzen {#start}

Ein Auftrag kann nur starten, solange sein Los nicht pausiert und nicht beendet ist, und nur, wenn Stück verfügbar sind, aus dem vorherigen Schritt oder, beim ersten Schritt, aus dem eingetroffenen Rohmaterial. Ein Poolauftrag braucht eine Maschine, nach der der Dialog **Fertigungsauftrag starten** fragt. Das Fortsetzen deiner eigenen Pause braucht dieselben Stück und ein Los, das nicht pausiert ist. Starten, Pausieren und Fertigmeldungen erfassen brauchen **Fertigungsaufträge schreiben**. Wie Fertigmeldungen erfasst werden, beschreibt [Fertigmeldungen erfassen](/handbook/production/completions).

## Eine Fertigmeldung korrigieren {#reverse}

Eine irrtümlich gebuchte Fertigmeldung nimmst du auf der Losseite mit **Stornieren** zurück, das nach einem **Grund** fragt. Beide Einträge bleiben erhalten. Das braucht **Fertigungsaufträge verwalten**, und ohne diese Berechtigung ist der Button deaktiviert, mit einem Tooltip. Eine Fertigmeldung lässt sich einmal stornieren, nur wenn sie keinen Ausschuss hatte, und nur, solange die nächste Position ihre Stück nicht verbraucht hat. Das Los darf weder pausiert noch beendet sein.

## Teilen und Zusammenführen {#split}

Einen eingeplanten Auftrag kannst du mit **Teilen** in zwei oder mehr Teile auf derselben Maschine aufteilen. Eingeplante Aufträge derselben Losposition auf derselben Maschine und im selben Pool lassen sich mit **Zusammenführen** wieder verbinden, und die zusammengeführten Aufträge werden storniert.

## Beispiele {#examples}

Ein Auftrag über 40 läuft. Der Bediener erfasst 30 Stück und danach 10 weitere, und der Auftrag ist **Abgeschlossen**. Die zweite Buchung war ein Irrtum, also storniert der Bediener sie mit einem Grund, und der Auftrag ist mit 30 Stück wieder **In Bearbeitung**.

Ein Los wird pausiert, während einer seiner Aufträge läuft. Der Auftrag ist **Pausiert** und lässt sich nicht für sich fortsetzen, bis das Los fortgesetzt wird.
