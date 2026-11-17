---
title: Fertigmeldungen erfassen
summary: Wie du fertige Stück an einem Fertigungsauftrag erfasst, wie eine Prüfung Stück in Nacharbeits- und Neufertigungs-Lose zurückweist und wie eine falsche Fertigmeldung storniert wird.
sourceRefs:
  - frontend/src/features/production/components/ProductionOrderCompletionDialog.vue
  - frontend/src/features/production/lots/components/lot-detail/ReverseCompletionDialog.vue
  - backend/src/modules/fulfillment/application/use_cases/production_order/record_production_order_completion.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/reverse_production_order_completion.py
lastVerified: 2026-11-10
---

Eine Fertigmeldung hält fest, wie viele Stück eines Fertigungsauftrags an einem Tag fertig wurden. **Abschließen** auf der Warteschlange oder auf der Seite einer Maschine, die Schaltfläche **Fertigstellen** an einem Schritt im Verwalten-Modus der Losseite und **Ergebnis erfassen** an einer QS-Aufgabe öffnen alle den Dialog **Fertigstellung erfassen**. Ein Auftrag nimmt Fertigmeldungen nur an, solange er **In Bearbeitung** ist und sein Los nicht pausiert ist. Das Erfassen braucht **Fertigungsaufträge schreiben**, und ohne diese Berechtigung sind die Schaltflächen deaktiviert und zeigen einen Tooltip.

## Stück erfassen {#record}

**Fertiggestellte Menge** startet mit dem, was der Auftrag noch buchen darf, seiner Menge abzüglich aller schon bearbeiteten Stück. Gib weniger ein, wenn nur ein Teil fertig ist. Der Auftrag bleibt **In Bearbeitung** und wird **Abgeschlossen**, sobald alle seine Stück gebucht sind. **Fertigstellungsdatum** ist von Haus aus heute und darf weder in der Zukunft noch vor dem Start des Auftrags liegen. **Bediener** erscheint nur an einem gemeinsamen Konto und muss das Mitglied nennen, das die Arbeit gemacht hat. **Notiz** ist optional.

Eine Position kann nur fertigmelden, was bei ihr angekommen ist. Der erste interne Schritt braucht eingetroffenes Rohmaterial, jeder spätere die guten Stück der Position davor. Jede Fertigmeldung merkt sich außerdem die Maschine, auf der der Auftrag lief.

## Zurückweisungen bei einer Prüfung {#rejects}

Nur eine Prüfposition weist Stück zurück, und das Erfassen dort braucht **Qualitätsprüfungen erfassen**. Ohne diese Berechtigung weist der Dialog darauf hin und bleibt nur lesbar. Gib **Angenommen** und **Zurückgewiesen** ein. Zurückgewiesene Stück brauchen einen **Grund der Zurückweisung**, und unter **Zurückgewiesene Stücke klassifizieren** bekommt jedes Stück **Nacharbeit** oder **Neufertigung**. Nacharbeitsstück gehen in ein neues Nacharbeits-Los, das sie repariert, Neufertigungen in ein neues Neufertigungs-Los, das sie neu fertigt. Die Bedarfsdeckung des Loses wandert zu den neuen Losen. Verlangt die Prüfmethode einen Nachweis, muss unter **Messprotokolle** eine Datei hochgeladen sein, bevor du erfassen kannst.

An jedem anderen Schritt werden schlechte Stück mit **Teile verschrotten** gebucht, siehe [Lebenszyklus eines Loses](/handbook/production/lot-lifecycle#scrapped).

## Eine Fertigmeldung stornieren {#reverse}

Auf der Seite des Loses listet der Reiter **Ausführung** die Fertigmeldungen jedes Auftrags mit einer Schaltfläche **Stornieren**. Sie braucht **Fertigungsaufträge verwalten** und ist ohne diese Berechtigung deaktiviert, mit einem Tooltip. **Fertigmeldung stornieren** fragt nach einem **Grund**, bucht die Stück zurück und behält beide Einträge, die ursprüngliche als storniert markiert. Ein Auftrag, der **Abgeschlossen** war, kehrt zu **In Bearbeitung** zurück. Eine Fertigmeldung lässt sich einmal stornieren. Das geht nicht, wenn sie Stück zurückgewiesen hat, wenn die nächste Position ihre Stück schon verwendet hat, oder solange das Los pausiert oder beendet ist.

## Beispiele

Von einem Auftrag über 40 Stück sind am Schichtende 25 fertig. Öffne **Abschließen**, ändere **Fertiggestellte Menge** auf 25 und klick auf **Erfassen**. Morgen startet der Dialog mit 15.

Eine Prüfung von 10 Stück findet 2 außerhalb der Toleranz. Gib 8 **Angenommen** und 2 **Zurückgewiesen** ein, wähl **Außerhalb der Toleranz** als Grund und setz ein Stück auf **Nacharbeit** und eines auf **Neufertigung**. Zwei neue Lose mit je einem Stück erscheinen.

Jemand hat 50 statt 5 Stück gebucht. Klick bei dieser Fertigmeldung auf **Stornieren**, gib den Grund ein und erfasse 5 erneut.
