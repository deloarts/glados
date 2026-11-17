---
title: Lebenszyklus eines Rohblock-Bedarfs
summary: Wie der Rohmaterialbedarf eines Loses entsteht, von offen über Zuteilung und Bestellung bis zur Erfüllung wandert, und was sein Abbrechen mit dem Los macht.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/demand.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/domain/services/demand_status_rules.py
  - backend/src/modules/fulfillment/application/use_cases/source_item_demand/cancel_source_item_demand.py
  - backend/src/modules/fulfillment/application/use_cases/source_item_demand/update_source_item_demand.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/approve_lot_source.py
  - backend/src/modules/fulfillment/application/use_cases/production_lot/switch_lot_material_source.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

Ein Rohblock-Bedarf ist das Rohmaterial, das ein Fertigungslos braucht, eine Zeile in der Liste **Rohblock Bedarf**. Er gehört zu einem Los und folgt den Regeln eines [Zukaufteile-Bedarfs](/handbook/procurement/bought-item-demand-lifecycle): Sein Status ergibt sich aus seinen Zuteilungen und den Bestellpositionen dahinter, jedes Mal, wenn sich eines davon ändert. Das Diagramm unten wird live aus den Regeln gelesen, nach denen das System arbeitet.

<StateMachineEmbed machine-key="source_item_demand_status" />

## Wann der Bedarf erscheint

Ein Los bekommt seinen Rohmaterialbedarf, sobald seine Materialquelle gesetzt ist, meist schon beim Anlegen des Loses aus einem Fertigungsteil mit Materialquelle. **Neuer Bedarf** in dieser Liste legt einen für ein Los von Hand an und braucht **Fertigungslose schreiben**. Hat dein Administrator **Freigabe für Rohblöcke erforderlich** eingeschaltet, bekommt ein Los mit einem Rohblock als Quelle keinen Bedarf, bis jemand seine Materialquelle freigibt. Ein Los, das auf die Freigabe wartet, hat hier also noch keine Zeile. Ein Los mit einem Zukaufteil als Quelle wird nie zurückgehalten. Wie die Freigabe funktioniert, steht unter [Materialquelle](/handbook/production/material-source).

## Was jeder Status bedeutet

**Offen**, **Zugeteilt**, **Bestellt**, **Erfüllt** und **Abgebrochen** bedeuten dasselbe wie bei einem Zukaufteile-Bedarf. Deckt eine Bestellposition Zukaufteile-Bedarfe und Rohmaterialbedarfe zugleich, bekommen die Zukaufteile-Bedarfe die eintreffenden Teile zuerst.

## Einen Status von Hand setzen

Von Hand setzt du nur **Erfüllt** und **Abgebrochen**, über **Status setzen**, wofür du **Bedarfsteile schreiben** und **Bedarfsteile verwalten** brauchst. **Bedarf stornieren** im Zeilenmenü und im Bedarfsdialog braucht stattdessen **Fertigungslose schreiben**. Ohne die Berechtigung ist die Aktion ausgegraut, und der Tooltip nennt, was fehlt. Wenn du einen Bedarf als erfüllt markierst, fragt Glados vorher nach, behält, was schon eingetroffen ist, und gibt den Rest seiner Zuteilungen auf Bestellpositionen frei. Bis ein Bedarf erfüllt oder abgebrochen ist, kannst du ihn bearbeiten, und seine Menge fällt nie unter das schon Zugeteilte.

Beim Abbrechen des Rohmaterialbedarfs eines Loses fragt Glados, was mit dem Los passieren soll. **Los auch stornieren** storniert das Los und seine offene Arbeit zusammen mit dem Bedarf und braucht zusätzlich **Fertigungslose verwalten**. **Nur den Bedarf stornieren** löst den Bedarf von seinem Los, das dann ohne Bedarf auf Rohmaterial wartet. Hat das Los die Fertigung schon begonnen, wird das Abbrechen abgelehnt, weil das Los dieses Material schon hält oder verbraucht: Ändere die Materialquelle oder schließe das Los zwangsweise ab.

Änderst du die Materialquelle eines Loses, dessen Rohmaterial schon zugeteilt oder bestellt ist, zeigt Glados zuerst, was schon eingetroffen ist. Das Eingetroffene bleibt beim Los, und der Bedarf gilt damit als erfüllt. Seine Zuteilungen auf Bestellpositionen, deren Stück noch nicht eingetroffen sind, werden freigegeben, damit der Einkauf diese Positionen stornieren oder mit Restmenge abschließen kann, und die neue Quelle bekommt einen Bedarf für das, was noch fehlt. Jede Aktion steht unter [Statusübergänge eines Rohblock-Bedarfs](/handbook/procurement/source-item-demand-transitions).

## Beispiele

**Ein einfaches Abbrechen.** Ein geplantes Los braucht seine Stahlstange nicht mehr. Du brichst den Bedarf ab, wählst **Los auch stornieren**, und Los und Bedarf enden gemeinsam.

**Ein anderes Material.** Ein Los ist noch in Planung und soll eine andere Stange verwenden. Du änderst seine Materialquelle, statt abzubrechen, und der alte Bedarf wird in einem Schritt ersetzt.

**Ein begonnenes Los.** Der erste Schritt ist schon gelaufen. Das Abbrechen wird abgelehnt, also änderst du die Materialquelle, und was eingetroffen ist, bleibt beim Los.
