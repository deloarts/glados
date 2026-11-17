---
title: Fertigung in Bearbeitung
summary: Was der Reiter WIP auflistet, wie er die Stück zählt, die noch roh, zwischen den Schritten oder fertig sind, und wie du ihn filterst.
sourceRefs:
  - frontend/src/features/production/wip/views/ProductionWipView.vue
  - frontend/src/features/production/wip/components/ProductionWipTable.vue
  - backend/src/modules/fulfillment/application/use_cases/production_order/get_production_wip.py
  - backend/src/modules/fulfillment/domain/services/production_wip_service.py
lastVerified: 2026-11-10
---

Der Reiter **WIP** unter Produktion zeigt, wo die Stück jedes Loses in Fertigung gerade sind. Er listet die Lose, die **Teilweise geplant**, **Geplant**, **In Bearbeitung** oder **Pausiert** sind, Entwürfe und abgeschlossene oder stornierte Lose bleiben also draußen. Die Liste zeigt nur an, ändern kannst du hier nichts.

## Was eine Zeile zeigt {#row}

Jede Zeile ist ein Los mit seiner **Losnummer**, dem **Artikel** mit Bild und Teilenummer, seinem **Status** und seiner **Priorität**. **Roh / Wartend** zählt die Stück, die der erste Schritt noch nicht abgeschlossen hat, also die Losmenge minus das, was der erste Schritt abgeschlossen hat. **Fertig** zählt die Stück, die der letzte Schritt abgeschlossen hat. Die Stück dazwischen sind irgendwo entlang der Kette.

Öffne den Pfeil am Anfang einer Zeile, um die Schritte des Loses zu sehen. Jeder Schritt zeigt seine **Pos.**, seine **Art**, seinen **Status**, unter **Menge** die abgeschlossenen Stück gegen seine Menge und unter **Maschine / Lieferant** die Maschinen, auf denen seine Aufträge laufen, oder den Lieferanten eines externen Schritts. Die Stück, die ein Schritt abgeschlossen hat, der nächste aber noch nicht, warten beim nächsten Schritt.

Ein Klick auf eine Zeile öffnet das Los.

## Filtern {#filters}

Die Felder unter den Spaltenköpfen filtern die Liste, während du tippst. **Losnummer** und **Artikel** suchen nach Text, **Status** und **Priorität** bieten die Werte an, die in der Liste vorkommen, und **Roh / Wartend** und **Fertig** nehmen in zwei kleinen Feldern ein Minimum und ein Maximum. **Zurücksetzen** löscht jeden Filter.

## Aktuell bleiben {#refresh}

Die Liste aktualisiert sich von selbst, sobald sich ein Los, ein Fertigungsauftrag oder eine Maschine ändert, sie kann also offen auf einem Bildschirm bleiben. Das Tag in der Leiste zeigt während des Ladens **Automatische Aktualisierung** und danach die Zeit der letzten Aktualisierung. **Synchronisieren** lädt sie von Hand neu, und schlägt eine Aktualisierung fehl, bleiben die Zeilen stehen und die Zeit zeigt, wie alt sie sind.

## Beispiele {#examples}

Ein Los über 20 Stück hat drei interne Schritte. Schritt 1 hat 20 abgeschlossen, Schritt 2 hat 12 und Schritt 3 hat 5. Die Zeile zeigt 0 unter **Roh / Wartend** und 5 unter **Fertig**. Von den 15 Stück dazwischen sind 8 bei Schritt 2 und 7 bei Schritt 3.

Ein Los wartet auf sein Rohmaterial, und noch kein Schritt hat etwas abgeschlossen. **Roh / Wartend** zeigt die ganze Losmenge und **Fertig** zeigt 0.

Ein Planer setzt den Filter **Roh / Wartend** auf ein Minimum von 1 und den Filter **Status** auf **In Bearbeitung**, um die laufenden Lose zu sehen, die noch Stück zum Starten haben.
