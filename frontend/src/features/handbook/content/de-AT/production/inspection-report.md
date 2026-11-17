---
title: Prüfbericht
summary: Was der Prüfbericht eines Fertigungsloses zeigt, wo du ihn öffnest und wann er vollständig ist.
sourceRefs:
  - frontend/src/features/production/lots/utils/inspectionReport.ts
  - frontend/src/shared/reports/components/ReportExportDialog.vue
  - backend/src/modules/fulfillment/domain/value_objects/lot_event_type.py
lastVerified: 2026-11-10
---

Der Prüfbericht eines Fertigungsloses fasst in einem PDF zusammen, was die Qualität für dieses Los zeigen muss: das Teil, sein Material, jede Prüfung mit ihren Ergebnissen und was mit zurückgewiesenen Teilen geschehen ist. Du gibst ihn einem Kunden mit der Lieferung mit oder legst ihn in die Losakte. Er entsteht im selben Exportdialog wie andere Berichte, siehe [Berichte exportieren und drucken](/handbook/resources/report-export).

## Den Bericht öffnen

Öffne **Prüfbericht** im Druckmenü eines Loses, im Untermenü **Drucken** seiner Zeile in der Lostabelle oder bei seiner Prüfaufgabe. Der Bericht lässt sich auch ohne die Berechtigung **Dokumente drucken** herunterladen. Zum Drucken brauchst du diese Berechtigung, ohne sie ist **Drucken** deaktiviert und zeigt einen Hinweis.

## Was er zeigt

Der Bericht beginnt mit einer Zusammenfassung des Loses, mit Projekt, Menge, Termin und wie viele Teile fertig und verschrottet sind. Dann zeigt er das Teil mit Bild, Revision und den Namen seiner Zeichnungen, und das Material mit Quelle, Bestellung und Freigabe. Danach folgt jede Prüfung mit Methode, Anweisung, Ergebnissen und prüfender Person. Zurückgewiesene Teile zeigen ihren Grund und ihre Entscheidung, und angehängte Nachweise stehen mit einem Fingerabdruck jeder Datei da, damit sich eine Kopie daran prüfen lässt. Die Fremdbearbeitung steht mit ihrem Wareneingang da, und jede Abweichung mit ihren Folgelosen für Nacharbeit oder Ersatz.

Wenn du zurückgewiesene Teile einer Prüfung erfasst, wähl den **Grund der Zurückweisung**; der Bericht zeigt ihn beim Ergebnis.

## Der Qualitätsverlauf

Der letzte Teil listet die Ereignisse, die für die Qualität zählen, in der Reihenfolge, in der sie geschehen sind, und wer sie ausgelöst hat. Das sind das Anlegen des Loses, die Freigabe oder Ablehnung seiner Materialquelle, ein Wechsel der Materialquelle, ein Anhalten und Fortsetzen, Prüfungen, verschrottete und beim Wareneingang verlorene Teile, Folgelose und wie das Los endete. Ein Los, das mit **Los abschließen** vorzeitig beendet wurde, zeigt zusätzlich **Teile in Arbeit verworfen** für Gutteile, die die nächste Position nie erreicht haben. Ein so beendetes oder mit **Los stornieren** beendetes Los zeigt **Rohmaterial übrig** für Rohmaterial, das angekommen ist, aber nicht verwendet wurde. Planungsänderungen bleiben draußen und stehen nur im Verlauf des Loses.

## Ein Los, das noch nicht fertig ist

Der Bericht zeigt nur, was Glados im Moment des Exports weiß. Ein noch nicht abgeschlossenes Los trägt oben einen Warnhinweis, dass der Bericht seinen Stand zum Zeitpunkt des Exports zeigt und keine abgeschlossene Prüfung. Exportier ihn noch einmal, wenn das Los fertig ist.

## Beispiele

**Für den Kunden.** Ein Los mit 40 Haltern ist fertig. Du öffnest **Prüfbericht** im Druckmenü, wählst English und klickst auf **PDF herunterladen**, dann hängst du die Datei an die Mail mit dem Lieferschein.

**Ein Los mit Nacharbeit.** Drei Teile sind bei der Maßprüfung mit dem Grund Bohrung versetzt durchgefallen. Der Bericht zeigt den Grund beim Ergebnis und listet das Nacharbeitslos unter den Abweichungen.

**Eine frühe Kopie.** Die Qualität will den Bericht, während das Los noch läuft. Das PDF trägt den Warnhinweis, dass es den Stand zum Zeitpunkt des Exports zeigt.
