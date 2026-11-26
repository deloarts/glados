---
title: Prüfmethoden
summary: Was eine Prüfmethode ist, wie ihre Standardzeiten, ihre QS-Maschine und die Nachweispflicht bei den Prüfschritten ankommen und wie die Reihenfolge der Liste funktioniert.
sourceRefs:
  - backend/src/modules/catalogue/application/use_cases/inspection_method/update_inspection_method.py
  - backend/src/modules/catalogue/application/use_cases/inspection_method/archive_inspection_method.py
  - backend/src/modules/catalogue/domain/policies/inspection_method_rules.py
  - backend/src/modules/catalogue/domain/services/label_name_rules.py
  - backend/src/modules/catalogue/application/services/catalogue_list_order.py
  - backend/src/modules/fulfillment/domain/policies/wait_after.py
lastVerified: 2026-11-26
---

Eine Prüfmethode ist eine Art von Qualitätsprüfung, etwa eine Sichtprüfung, eine Prüfung mit der Gewindelehre oder eine Messung am Koordinatenmessgerät. Jeder Prüfschritt eines Loses verwendet eine. Die Methode bringt die Standardwerte mit, mit denen ein neuer Prüfschritt startet, und legt fest, ob ein Abschluss ein Messprotokoll braucht. Die Liste findest du unter Ressourcen, **Prüfmethoden**.

## Name, Beschreibung und Farben

Jede Methode hat einen **Name** und eine **Beschreibung** in jeder Sprache der Oberfläche. Der Name ist in der Standardsprache Pflicht und darf bis zu 200 Zeichen lang sein. Zwei Methoden, die nicht archiviert sind, dürfen in derselben Sprache nicht denselben Namen zeigen, Groß- und Kleinschreibung egal. **Label-Farbe** und **Schriftfarbe** legen fest, wie die Methode als Label erscheint, und die **Vorschau** zeigt das Ergebnis.

## Standardzeiten

**Standard-Rüstzeit [min]** und **Standard-Stückzeit [min]** sind optional. Die Rüstzeit nimmt ganze Minuten, die Stückzeit Minuten mit bis zu zwei Nachkommastellen, und beide nehmen 0 oder mehr. Sie werden nur auf neue Prüfschritte übernommen, wo du sie je Schritt noch ändern kannst; änderst du die Methode später, bleiben bestehende Schritte unverändert. Bleibt ein Feld leer, hat der Schritt für diesen Teil keine Zeitschätzung.

## Standard-QS-Maschine

**Standard-QS-Maschine** ist optional und zeigt leer Keine Maschine (manuelle Prüfung). Angeboten werden nur Maschinen, die als QS- oder Messmaschine gekennzeichnet sind. Wird ein Los angelegt, wird die Maschine beim Fertigungsauftrag seines Prüfschritts eingetragen. Ohne Maschine bleibt die Prüfung Handarbeit, denn Auto-Plan sucht für Prüfarbeit nie selbst eine Maschine aus.

## Nachweis erforderlich

Hak **Nachweis erforderlich** an, wenn eine Prüfung dokumentiert sein muss. Ein Abschluss für einen Schritt mit dieser Methode lässt sich erst buchen, wenn mindestens eine Messprotokoll-Datei am Fertigungsauftrag hängt.

## Warten nach der Prüfung {#wait-after}

**Wartezeit nach der Prüfung [min]** ist optional und bei neuen Methoden leer. Trag die Minuten ein, die die Teile nach einer Prüfung mit dieser Methode warten müssen, bevor der nächste Schritt beginnen kann, etwa auf ein Laborergebnis. Die Wartezeit läuft nach der Uhr, also auch über Nacht und am Wochenende, und der nächste Schritt wird für ihr Ende geplant, auch wenn die Prüfung selbst schon fertig gemeldet ist. Ist die Prüfung der letzte Schritt eines Loses, gilt das Los als verspätet, bis die Wartezeit vorbei ist, und nach jeder gespeicherten Änderung wird der Zeitplan neu berechnet.

## Die Liste verwalten

Zum Anlegen, Bearbeiten, Verschieben, Archivieren und Wiederherstellen von Methoden brauchst du die Berechtigung **Prüfmethoden schreiben**. Ohne sie sind die Schaltflächen deaktiviert. Methoden werden archiviert, nicht gelöscht, damit bestehende Schritte ihre behalten. Eine Methode lässt sich nicht archivieren, solange sie die **Standard-Prüfmethode** in den Produktionseinstellungen ist; wähl dort zuerst einen anderen Standard. **Archivierte anzeigen** listet archivierte Methoden wieder auf, und das Wiederherstellen wird abgelehnt, solange eine aktive Methode denselben Namen trägt. Ein Klick auf eine Zeile öffnet die Details.

In der Reihenfolge der Liste bieten die Auswahlfelder die Methoden an. Darfst du Prüfmethoden bearbeiten, zieh eine Zeile am Griff in ihrer ersten Spalte an ihren neuen Platz. Der Griff erscheint nur, solange keine Sortierung, Suche und kein Filter aktiv ist. Neue Methoden kommen ans Ende.

## Beispiele

**Eine Sichtprüfung.** Leg Sichtprüfung mit 0 bei **Standard-Rüstzeit [min]** und 0,5 bei **Standard-Stückzeit [min]** an. Ein neuer Prüfschritt für 40 Stück startet mit einer Schätzung von 20 Minuten, und die Prüferin kann sie am Schritt anpassen.

**Messen mit Nachweis.** Leg KMG-Messung an, wähl deine Messmaschine als **Standard-QS-Maschine** und hak **Nachweis erforderlich** an. Neue Lose legen ihre Prüfung auf diese Maschine, und der Schritt lässt sich erst abschließen, wenn das Protokoll angehängt ist.

**Warten auf ein Laborergebnis.** Leg Salzsprühtest mit 2880 bei **Wartezeit nach der Prüfung [min]** an, also zwei Tage. Eine Endprüfung, die am Montag um 10:00 endet, hat ihr Ergebnis am Mittwoch um 10:00, ein Los mit Zieltermin Mittwoch ist also pünktlich. Endet sie erst am Dienstagnachmittag, gilt dasselbe Los als verspätet.

**Den Standard ablösen.** Du willst Endprüfung archivieren, die gerade die **Standard-Prüfmethode** ist. Glados lehnt ab. Setz in den Produktionseinstellungen einen anderen Standard und archivier sie dann.
