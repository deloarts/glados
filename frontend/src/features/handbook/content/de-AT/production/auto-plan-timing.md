---
title: Wann ein Auftrag starten kann
summary: Wie das geplante Zeitfenster eines Fertigungsauftrags aus seinem vorherigen Schritt, seinem Material, der Maschinenwarteschlange und dem Maschinenkalender entsteht.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/scheduling/forward_walk.py
  - backend/src/modules/fulfillment/domain/services/scheduling/machine_calendar.py
  - backend/src/modules/fulfillment/application/use_cases/production_schedule/auto_plan.py
  - backend/src/modules/fulfillment/domain/policies/wait_after.py
lastVerified: 2026-11-26
---

Jeder Fertigungsauftrag in einer Warteschlange bekommt ein geplantes Zeitfenster, seinen Start und sein Ende. Glados berechnet diese Zeitfenster neu, sobald sich etwas ändert, das sie verschieben kann, und [Auto-Planen](/handbook/production/auto-plan) verwendet dieselben Regeln, nachdem es seine Aufträge eingeplant hat. Diese Seite erklärt, was einen Auftrag aufhält und wie seine Arbeitszeit auf den Kalender verteilt wird.

## Worauf ein Auftrag wartet {#waits}

Ein Auftrag startet zum spätesten von vier Zeitpunkten. Der erste ist sein eigenes Datum **Nicht vor**, wenn ein Planer eines gesetzt hat. Der zweite ist, wann die Teile seines vorherigen Schritts bereit sind. Ein Schritt in der Eigenfertigung gibt seine Teile weiter, wenn sein letzter Auftrag enden soll, plus die Wartezeit, die seine Methode festlegt, etwa zum Aushärten, plus die **Übergabe zwischen Schritten der Eigenfertigung (Minuten)**. Ein externer Schritt ist an seinem Liefertag fertig, sonst an seinem Abholbereit-Datum, sonst an seinem erwarteten Liefertermin. Der dritte ist, nur beim ersten Schritt, das Eintreffen des Rohmaterials. Der vierte ist das Ende der Arbeit, die auf derselben Maschine schon vor ihm wartet. Ein Schritt ohne Maschine, Handarbeit oder eine Prüfung, hat keine solche Warteschlange und wartet nur auf sein eigenes Los.

Die **Reaktionszeit für geplanten Start (Tage)** kommt nach der Lieferung eines Lieferanten und nach dem Eintreffen des Materials dazu, denn Teile, die heute ankommen, sind heute noch nicht bereit für den nächsten Schritt. Ein erwarteter Liefertag, der vorbei ist, ohne dass etwas angekommen ist, zählt als heute, der nächste Schritt rückt also Tag für Tag hinaus, bis die Lieferung kommt. Ein wartender Auftrag startet nie vor jetzt.

Ein Auftrag bleibt ohne Termine, wenn ein früherer Schritt gar keinen Termin hat oder wenn sein Rohmaterial weder eingetroffen noch mit einem Liefertermin bestellt ist. Termine bekommt er, sobald schon Teile an seinem Schritt warten.

## Arbeitszeit {#calendar}

Ab seinem Start verbraucht der Auftrag seine geschätzte Zeit auf dem Arbeitskalender der Maschine. Das ist die eigene Arbeitswoche der Maschine, wenn sie eine hat, sonst die Standard-Arbeitswoche, und darüber liegen die Datumsausnahmen der Maschine. Feiertage und Betriebsurlaube unter **Feiertage** in **Ressourcen** schließen jede Maschine, außer die eigene Ausnahme der Maschine öffnet sie an diesem Tag. Ausfallzeiten werden aus dem Kalender herausgeschnitten, und eine Maschine, die beim Start von Auto-Planen ausgefallen ist, bleibt bei diesem Lauf außen vor. Tage ohne Arbeitszeit werden übersprungen, ein langer Auftrag läuft also in die nächsten Arbeitstage weiter. Die Stunden sind Werkszeit, und eine Nachtschicht über Mitternacht zählt für den Tag, an dem sie beginnt.

Manuelle Schritte brauchen keine Maschine und verwenden die Standard-Arbeitswoche, jeder für sich. Eine Maschine, deren Kalender gar keine Arbeitszeit enthält, etwa eine Woche mit null Stunden, bekommt für ihre Aufträge keine Termine, und diese werden markiert.

## Aufträge, die ihr Zeitfenster behalten {#kept}

Ein laufender Auftrag bleibt bei dem Zeitpunkt, zu dem er zuletzt gestartet oder fortgesetzt wurde. Läuft er zu lange, rückt sein Ende hinaus: sind schon Teile gemeldet, auf jetzt plus die Teile, die noch fehlen, sonst auf jetzt, und die Schritte danach rücken mit. Ein pausierter Auftrag verbraucht keine Zeit. Ein angehefteter Auftrag behält sein Zeitfenster, und das gilt auch für einen wartenden Auftrag, der innerhalb des **Fixierter Zeitraum (Stunden)** startet, außer Auto-Planen oder ein Planer verschiebt ihn. Der Auftrag nach einem behaltenen Zeitfenster startet trotzdem erst nach dem Auftrag davor, und ein behaltenes Zeitfenster, das seinen Nachbarn überlappt, wird markiert.

## Beispiele {#examples}

Der erste Schritt eines Loses ist Eigenfertigung und endet am Dienstag um 14:00, die Übergabe ist 0 Minuten. Auf einer freien Maschine startet der zweite Schritt am Dienstag um 14:00, gleich danach.

Das Rohmaterial eines Loses ist mit dem Liefertermin 12. bestellt. Sein erster Schritt kann mit einem Tag Reaktionszeit am 13. starten. Hätte das Material keinen Liefertermin, bliebe der erste Schritt ohne Termine, bis es jemand mit einem bestellt.

Ein Härteschritt sollte am Montag zurückkommen, aber bis Mittwoch ist nichts angekommen. Mit einem Tag Reaktionszeit wird der Schritt danach für Donnerstag geplant, und er rückt jeden Tag, an dem die Lieferung ausbleibt, einen Tag weiter.

Ein Klebeschritt, dessen Methode 720 Minuten Wartezeit hat, endet am Montag um 15:00. Der Schritt danach startet am Dienstag um 08:00, zur ersten Arbeitsstunde nach den zwölf Stunden.
