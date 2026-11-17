---
title: Ausdrucke und Verteiler
summary: Wo jeder Download und jeder Ausdruck eines Berichts festgehalten wird, wie ein Bericht aussieht und welche Revision und welche Ergebnisse er zeigt.
sourceRefs:
  - backend/src/modules/quality/application/use_cases/print_document/get_print_jobs.py
  - backend/src/modules/quality/application/use_cases/report_journal/record_report_download.py
  - frontend/src/shared/reports/components/ReportDistribution.vue
  - frontend/src/shared/reports/utils/reportDocument.ts
  - frontend/src/features/tools/utils/toolReport.ts
  - frontend/src/features/checklists/utils/report.ts
lastVerified: 2026-11-10
---

Ein Bericht einer gespeicherten Berechnung oder Prüfliste hinterlässt bei jedem Download und jedem Druck eine Spur in Glados, damit du später weißt, wer welche Kopie hat. Diese Seite erklärt diese Einträge und was ein Bericht trägt. Wie du einen Bericht exportierst oder druckst, steht unter [Berichte exportieren und drucken](/handbook/resources/report-export).

## Wo Ausdrucke protokolliert werden

Jeder Druck, ob gesendet oder fehlgeschlagen, steht im **Druckverlauf** seines Druckers. Klick unter Ressourcen, **Drucker** mit der rechten Maustaste auf den Drucker und wähl **Druckverlauf**, dann siehst du, wer welchen Datensatz wann in wie vielen Kopien gedruckt hat. Zum Öffnen brauchst du **Einstellungen lesen**. Mehr zum Verlauf steht unter [Drucker](/handbook/resources/printers#history).

## Wohin Berichte eines Datensatzes gingen {#distribution}

Jeder Download und jeder Druck einer gespeicherten Berechnung oder Prüfliste kommt in ihren Verteiler: wer, wann, welche Revision, in welcher Sprache und mit welchen Optionen, und ein Fingerabdruck der Datei. Glados bewahrt das PDF selbst nicht auf. Eine freigegebene Revision ändert sich nie mehr, deshalb lässt sich derselbe Bericht jederzeit wieder erzeugen. Klick bei der Berechnung oder Prüfliste auf **Verlauf** und öffne **Verteilung**, um die Liste zu sehen. Eine Kopie, die später auftaucht, ordnest du über den Anfang ihres Fingerabdrucks ihrem Eintrag zu. Downloads nicht gespeicherter Eingaben stehen nicht in der Liste.

## Wie ein Bericht aussieht

Ein Bericht sieht für alle gleich aus, egal welches Theme, welchen Browser oder welchen Drucker du verwendest. Er trägt Logo und Namen der Firma, die Angaben zum Datensatz, etwa wer ihn wann freigegeben hat, und wer ihn an welchem Tag exportiert hat.

Jede Seite des Berichts eines gespeicherten Datensatzes trägt in der Fußzeile einen QR-Code, daneben die Referenz des Datensatzes und einen Hinweis, dass die Seite eine ausgedruckte Kopie ist. Scann ihn mit deinem Handy oder dem Scanner in Glados, dann öffnet sich genau die Revision, die gedruckt wurde. Gibt es eine neuere Revision, sagt dir die Seite das und verlinkt sie. Ein Bericht aus nicht gespeicherten Eingaben hat keinen QR-Code.

Er wird als PDF/A geschrieben, dem Archivformat, das alles Nötige in der Datei selbst enthält, damit sie auch in vielen Jahren gleich aussieht. Leg das PDF in die technischen Unterlagen, nicht einen Scan eines Ausdrucks.

## Wenn die heutigen Ergebnisse abweichen

Ein Berechnungsbericht wird aus den gespeicherten Eingaben neu berechnet. Weichen die heutigen Ergebnisse von den gespeicherten ab, listet die Berechnungsseite die Unterschiede auf und **Drucken** bleibt ausgegraut, bis du die Berechnung erneut speicherst, oder bis du eine neue Revision beginnst, wenn sie freigegeben ist. Aus einer Liste **Berechnungen** gedruckt, warnt der Bericht oben, dass er die heutigen Ergebnisse zeigt.

## Welche Revision einer Prüfliste gedruckt wird

Ein Prüflistenbericht zeigt die Revision, die du offen hast, und eine Liste **Prüflisten** druckt die neueste. Für eine ältere Revision öffne sie unter **Revisionen** und klick dort auf **Drucken**.

## Beispiele

**Wer eine Kopie hat.** Ein Auditor fragt, wer die Sicherheitsprüfliste bekommen hat. Du öffnest ihren **Verlauf**, wählst **Verteilung** und siehst zwei Downloads und einen Druck der Revision B, jeweils mit Datum und Person.

**Ein Ausdruck in der Halle.** Du scannst den QR-Code in seiner Fußzeile. Glados öffnet die gedruckte Revision und sagt dir, dass es eine neuere gibt, also tauschst du die Kopie aus.

**Heute andere Ergebnisse.** Eine ältere Berechnung der Antriebsauslegung liefert jetzt andere Ergebnisse. Ihre Seite listet die Unterschiede, und **Drucken** bleibt ausgegraut, bis du sie erneut speicherst.
