---
title: KPIs
summary: Welche Fertigungskennzahlen der Reiter KPIs zeigt, wie Zeitraum und Filter sie eingrenzen und wie du eine Kachel, ein Diagramm und die Tabelle der verspäteten Lose liest.
sourceRefs:
  - frontend/src/features/production/kpi/views/ProductionKpiView.vue
  - frontend/src/features/production/kpi/components/KpiFiltersBar.vue
  - frontend/src/features/production/kpi/utils/periodPresets.ts
  - backend/src/modules/quality/application/use_cases/production_kpi/compute_production_kpis.py
  - backend/src/modules/quality/domain/services/kpi_rules.py
lastVerified: 2026-11-10
---

Der Reiter **KPIs** unter Produktion misst, wie gut die Fertigung ihre Termine gehalten, ihre Maschinen genutzt und gute Teile gemacht hat. Jede Zahl entsteht aus den bereits erfassten Aufträgen, Fertigmeldungen und Lieferungen, eingeben musst du hier also nichts, und die Kacheln folgen den Definitionen der ISO 22400.

## Zeitraum und Umfang wählen {#filters}

**Zeitraum** wählt **Diese Woche**, **Letzte Woche**, **Dieser Monat**, **Letzter Monat**, **Letzte 90 Tage** oder **Benutzerdefiniert**, und der Reiter öffnet mit Dieser Monat. **Maschine / Pool** grenzt die Zahlen auf eine Maschine oder einen Pool ein, **Projekt** und **Kunde** auf ein Projekt oder einen Kunden. **Zurücksetzen** kehrt zu Dieser Monat ohne Eingrenzung zurück, und **Synchronisieren** lädt die Zahlen neu.

## Eine Kachel lesen {#tiles}

Die Kacheln oben sind **Terminplantreue**, **Liefertreue**, **Durchlaufzeit**, **Auslastung**, **First Pass Yield**, **Ausschussquote** und **Nacharbeitsquote**. **Verfügbarkeit** und **OEE** kommen dazu, sobald genug Daten für ihre Berechnung da sind. Fahr mit der Maus über das Info-Symbol einer Kachel, um ihre genaue Definition zu sehen. Die kleine Zeile unter dem Wert sagt, auf wie vielen Aufträgen, Losen oder Stück er beruht.

Die Veränderung neben dem Wert vergleicht ihn mit dem vorherigen Zeitraum gleicher Länge. Sie ist grün, wenn die Zahl besser geworden ist, und rot, wenn sie schlechter geworden ist, eine steigende Ausschussquote ist also rot. Eine Kachel mit **k. A.** hat im Zeitraum nichts zu messen, und die Zeile darunter sagt warum.

## Diagramme und Tabellen {#panels}

Das Wochendiagramm stellt Terminplantreue und Liefertreue je Kalenderwoche nebeneinander, und das Maschinendiagramm zeigt Auslastung und Verfügbarkeit je Maschine. **Schätzgenauigkeit je Fertigungsverfahren** vergleicht die echte Arbeitszeit mit der Schätzung, ein Verhältnis über 100 % heißt, die Arbeit hat länger gedauert. **Wartezeit zwischen Arbeitsschritten** zeigt, wie lange ein Auftrag wartet, nachdem der Schritt davor bereit ist. **Qualität je Artikel**, **Ausschuss nach Ursache** und **Zurückweisungen bei Wareneingang je Lieferant** zeigen, wo Teile verloren gingen.

**Verspätete & gefährdete Lose** listet die offenen Lose, deren geplantes Ende nach ihrem Zieltermin liegt, die mit den meisten Tagen Verspätung zuerst, zusammen mit der **Ursache**, die sie aufhält. Der Zeitraum gilt hier nicht, weil die Tabelle den Plan zeigt, wie er heute steht.

## Beispiele {#examples}

Eine Planerin öffnet den Reiter am ersten Arbeitstag eines Monats. Dieser Monat hat noch kaum Daten, also wechselt sie auf **Letzter Monat**, um den gerade beendeten Monat anzusehen.

Die Terminplantreue zeigt 72 % mit einem roten Pfeil. Stellst du **Maschine / Pool** der Reihe nach auf jede Maschine, siehst du, welche Maschine ihre Aufträge zu spät fertig hatte.

Ein Los steht unter Verspätete & gefährdete Lose mit der Ursache **Material fehlt**. Das Material ist noch nicht da, und das Los bleibt verspätet, bis es eintrifft.
