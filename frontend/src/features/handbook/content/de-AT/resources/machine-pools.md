---
title: Maschinenpools
summary: Was ein Maschinenpool ist, welche Arbeit er übernehmen kann und wie Auto-Plan und die Werkstatt ihn nutzen.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/machine_pool/create_pool.py
  - backend/src/modules/fulfillment/application/use_cases/machine_pool/update_pool.py
  - backend/src/modules/fulfillment/domain/services/machine_pool_rules.py
  - backend/src/modules/fulfillment/application/use_cases/machine_pool/place_pool.py
lastVerified: 2026-11-10
---

Ein Maschinenpool fasst Maschinen zusammen, die einander vertreten können, etwa drei ähnliche Drehmaschinen. Du weist einen Auftrag dem Pool statt einer einzelnen Maschine zu, und er läuft auf dem Mitglied, das Zeit hat. Die Liste findest du unter Ressourcen, **Maschinenpools**.

## Einen Pool einrichten

**Name** ist Pflicht, und zwei Pools dürfen gleich heißen, also wähl einen Namen, der sie unterscheidet. **Maschinen** wählt die Mitglieder. Eine archivierte Maschine lässt sich trotzdem wählen, mit einer Warnung, und ein Pool darf auch noch keine Mitglieder haben. **Notiz** ist optional.

## Welche Arbeit ein Pool übernimmt

Ein Pool übernimmt nur die Fertigungsmethoden, die jedes Mitglied hat. Kann eine Drehmaschine auch fräsen und die anderen nicht, übernimmt der Pool Drehen, aber nicht Fräsen. Ein Pool ohne Mitglieder übernimmt nichts. Prüfarbeit und Handarbeit kommen nie in einen Pool: Prüfarbeit geht an eine QS-Maschine, und Handarbeit braucht gar keine Maschine.

## Wie die Planung einen Pool nutzt

Jeder Auftrag eines Pools läuft auf einem seiner Mitglieder, das Arbeitszeit hat. Auto-Plan hat eine **Planungsebene**. Bei **Pools**, dem Standard im Dialog, bleibt ein Auftrag beim Pool, und welches Mitglied ihn übernimmt, bleibt offen. Bei **Maschinen** legt Auto-Plan den Auftrag auf ein Mitglied, das die Arbeit kann.

Pools tauchen auch auf, wenn du ein Los zuweist, in der Fertigungswarteschlange, auf den Maschinentafeln der Infoscreens und im Maschinenfilter der **KPIs**.

## Die Liste verwalten

Zum Anlegen, Bearbeiten, Archivieren und Wiederherstellen von Pools brauchst du die Berechtigung **Fertigungsmaschinen schreiben**. Ohne sie sind die Schaltflächen deaktiviert. Nichts blockiert das Archivieren eines Pools. **Archivierte anzeigen** listet archivierte Pools wieder auf. Die Spalte **Maschinen** filtert die Liste nach Mitglied. Nach dem Ändern, Archivieren oder Wiederherstellen eines Pools wird der Zeitplan neu berechnet.

In der Reihenfolge der Liste bieten die Auswahlfelder die Pools an. Darfst du Pools bearbeiten, zeigt die erste Spalte in jeder Zeile einen Griff. Halt den Griff fest und zieh die Zeile an ihren neuen Platz; eine Linie zeigt, wo sie landet. Der Griff erscheint nur, solange keine Sortierung, Suche und kein Filter aktiv ist, weil die Zeilen dann in einer anderen Reihenfolge stehen. Neue Pools kommen ans Ende.

## Beispiele

**Drei Drehmaschinen.** Leg den Pool Drehen mit deinen drei Drehmaschinen unter **Maschinen** an. Ein Drehauftrag, der dem Pool Drehen zugewiesen ist, läuft auf der Drehmaschine, die als erste Zeit hat.

**Ein Mitglied, das mehr kann.** Eine der Drehmaschinen kann auch fräsen. Der Pool übernimmt trotzdem nur Drehen, weil Fräsen keine Methode jedes Mitglieds ist. Weis Fräsarbeit dieser Drehmaschine direkt zu.

**Eine Drehmaschine geht.** Du archivierst eine Drehmaschine. Sie bleibt Mitglied, bis du sie herausnimmst, und das Formular des Pools zeigt bei ihr eine Warnung, also nimm sie unter **Maschinen** heraus, damit der Pool aufgeräumt bleibt.
