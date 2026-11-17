---
title: Exporting and Printing Reports
summary: How to turn a calculation, a checklist or an inspection report into a PDF, download it or send it to a document printer.
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

The "Export report" dialog turns a calculation or a checklist into a PDF report to download or to send to a document printer. Reports exist for drive sizing, safety distance, the checklists and the [inspection report](/handbook/production/inspection-report) of a production lot. Where every copy is logged and how a report looks is on [Printed Copies and Distribution](/handbook/resources/report-records).

## Opening the dialog

Click **Print** above an open calculation or checklist, or the printer button of a row on the **Calculations** and **Checklists** tabs of a project or a product. The drive sizing and safety distance tools under **Tools** have **Print** too. While a saved record has unsaved changes, **Print** stays greyed out, so the report always matches the record.

## Language and options

**Language** starts on the language of the app. Pick another one, and the report with its dates and numbers follows it.

Extra content stays off unless you tick it. The safety distance report can **Add the reference tables as an appendix**, and a checklist report can **Add the explanations of the items**. Your ticks are remembered in this browser.

## Downloading

**Download PDF** saves the report under its title and today's date. Everyone can download, even an unsaved calculation.

## Printing

Choose the **Printer**, up to 10 **Copies** and whether to **Print both sides**, then click **Print**. A message confirms which printer got the job, and the dialog remembers the printer and the both sides choice. When no document printer is set up, the dialog says so and you download the PDF instead.

Printing needs the permission **Print Documents**. Without it the printer choice is hidden, and **Print** shows disabled with a tooltip that names the permission.

**Print both sides** is greyed out for a printer connected without IPP. Such a printer only receives the file and cannot be told to use both sides.

## Why only saved records can be printed

Every printed copy is logged against its calculation or checklist, and the app checks that you may see that record. A calculation that was never saved has no record yet, so save it first or print the downloaded PDF yourself. The dialog then says so in place of the printer choice.

## Examples

**A released calculation.** Open the drive sizing calculation, click **Print**, choose the office printer, 2 copies and **Print both sides**, then **Print**. The printer's **Print History** lists it with 2 copies under your name.

**An unsaved check.** You try out a safety distance under **Tools** and click **Print**. Only a saved record can be printed, so you click **Download PDF** and mail the file.

**A checklist for a German speaking customer.** On the **Checklists** tab of the project, click the printer button of the checklist, pick **Deutsch**, tick **Add the explanations of the items** and click **Download PDF**.
