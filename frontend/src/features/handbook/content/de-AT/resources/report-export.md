---
title: Berichte exportieren und drucken
summary: Wie du aus einer Berechnung, einer Prüfliste oder einem Prüfbericht ein PDF machst, es herunterlädst oder an einen Dokumentdrucker schickst.
sourceRefs:
  - backend/src/modules/quality/application/use_cases/print_document/print_uploaded_document.py
  - backend/src/modules/quality/application/services/uploaded_document_roots.py
  - backend/src/modules/quality/domain/services/printer_rules.py
  - frontend/src/shared/reports/components/ReportExportDialog.vue
  - frontend/src/shared/reports/utils/reportDocument.ts
  - frontend/src/features/tools/utils/toolReport.ts
  - frontend/src/features/checklists/utils/report.ts
lastVerified: 2026-11-10
---

Der Dialog "Bericht exportieren" macht aus einer Berechnung oder einer Prüfliste einen PDF-Bericht, den du herunterlädst oder an einen Dokumentdrucker schickst. Berichte gibt es für die Antriebsauslegung, den Sicherheitsabstand, die Prüflisten und den [Prüfbericht](/handbook/production/inspection-report) eines Fertigungsloses. Wo jede Kopie festgehalten wird und wie ein Bericht aussieht, steht unter [Ausdrucke und Verteiler](/handbook/resources/report-records).

## Den Dialog öffnen

Klick auf **Drucken** über einer offenen Berechnung oder Prüfliste, oder auf den Druckerknopf einer Zeile in den Tabs **Berechnungen** und **Prüflisten** eines Projekts oder Produkts. Auch die Werkzeuge Antriebsauslegung und Sicherheitsabstand unter **Werkzeuge** haben **Drucken**. Solange ein gespeicherter Datensatz ungespeicherte Änderungen hat, bleibt **Drucken** ausgegraut, damit der Bericht immer zum Datensatz passt.

## Sprache und Optionen

**Sprache** steht zuerst auf der Sprache der App. Wählst du eine andere, folgt ihr der Bericht samt Datumsangaben und Zahlen.

Zusätzliche Inhalte bleiben aus, solange du sie nicht anhakst. Der Bericht zum Sicherheitsabstand kann **Referenztabellen als Anhang anfügen**, ein Prüflistenbericht kann **Erläuterungen zu den Punkten anfügen**. Deine Häkchen merkt sich dieser Browser.

## Herunterladen

**PDF herunterladen** speichert den Bericht unter seinem Titel und dem heutigen Datum. Herunterladen kann jeder, auch eine ungespeicherte Berechnung.

## Drucken

Wähl den **Drucker**, bis zu 10 **Kopien** und ob du **Beidseitig drucken** willst, dann klick auf **Drucken**. Eine Meldung bestätigt, welcher Drucker den Auftrag bekommen hat, und der Dialog merkt sich den Drucker und die Wahl für beidseitigen Druck. Ist kein Dokumentdrucker eingerichtet, sagt der Dialog das, und du lädst das PDF stattdessen herunter.

Zum Drucken brauchst du die Berechtigung **Dokumente drucken**. Ohne sie ist die Druckerauswahl ausgeblendet, und **Drucken** ist deaktiviert und nennt in einem Hinweis die Berechtigung.

**Beidseitig drucken** ist bei einem Drucker ausgegraut, der ohne IPP angebunden ist. So ein Drucker bekommt nur die Datei und lässt sich nicht anweisen, beide Seiten zu bedrucken.

## Warum nur gespeicherte Datensätze gedruckt werden können

Jeder Ausdruck wird bei seiner Berechnung oder Prüfliste protokolliert, und die App prüft, ob du diesen Datensatz sehen darfst. Eine nie gespeicherte Berechnung hat noch keinen Datensatz, also speichere sie zuerst oder drucke das heruntergeladene PDF selbst. Der Dialog sagt das dann anstelle der Druckerauswahl.

## Beispiele

**Eine freigegebene Berechnung.** Öffne die Berechnung der Antriebsauslegung, klick auf **Drucken**, wähl den Bürodrucker, 2 Kopien und **Beidseitig drucken**, dann **Drucken**. Der **Druckverlauf** des Druckers führt den Bericht mit 2 Kopien unter deinem Namen.

**Eine ungespeicherte Prüfung.** Du probierst unter **Werkzeuge** einen Sicherheitsabstand aus und klickst auf **Drucken**. Nur gespeicherte Datensätze können gedruckt werden, also klickst du auf **PDF herunterladen** und schickst die Datei per Mail.

**Eine Prüfliste für einen englischsprachigen Kunden.** Klick im Tab **Prüflisten** des Projekts auf den Druckerknopf der Prüfliste, wähl **English**, hak **Erläuterungen zu den Punkten anfügen** an und klick auf **PDF herunterladen**.
