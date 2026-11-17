---
title: Printed Copies and Distribution
summary: Where every download and printed copy of a report is recorded, how a report looks and which revision and results it shows.
sourceRefs:
  - backend/src/modules/quality/application/use_cases/print_document/get_print_jobs.py
  - backend/src/modules/quality/application/use_cases/report_journal/record_report_download.py
  - frontend/src/shared/reports/components/ReportDistribution.vue
  - frontend/src/shared/reports/utils/reportDocument.ts
  - frontend/src/features/tools/utils/toolReport.ts
  - frontend/src/features/checklists/utils/report.ts
lastVerified: 2026-11-10
---

A report of a saved calculation or checklist leaves a trace in Glados each time it is downloaded or printed, so you can tell later who has which copy. This page explains those records and what a report carries. How to export or print one is on [Exporting and Printing Reports](/handbook/resources/report-export).

## Where printed copies are logged

Every print, sent or failed, is listed in the **Print History** of its printer. Right click the printer under Resources, **Printers** and choose **Print History** to see who printed which record, how many copies and when. Opening it needs **Read Settings**. More on the history is on [Printers](/handbook/resources/printers#history).

## Where reports of a record went {#distribution}

Every download and print of a saved calculation or checklist is written to its distribution list: who, when, which revision, in which language and with which options, and a fingerprint of the file. Glados does not keep the PDF itself. A released revision never changes, so the same report can be produced again. Click **History** on the calculation or checklist and open **Distribution** to see the list. A copy that turns up later can be matched to its entry by the start of its fingerprint. Downloads of unsaved inputs are not listed.

## How a report looks

A report looks the same for everyone, whatever theme, browser or printer you use. It carries the company logo and name, the record's details such as who released it and when, and who exported it on which day.

Every page of a saved record's report carries a QR code in its footer, with the record's reference next to it and a line saying the page is a printed copy. Scan it with your phone or the scanner in Glados to open exactly the revision that was printed. If a newer revision exists, the page tells you so and links to it. A report of unsaved inputs has no QR code.

It is written as PDF/A, the archival format, which holds everything it needs in the file itself, so it looks the same in many years. Keep the PDF in the technical file rather than a scan of a printout.

## When today's results differ

A calculation report is recalculated from the saved inputs. If today's results differ from the saved ones, the calculation page lists the differences and keeps **Print** greyed out until you save it again, or start a new revision if it is released. Printed from a **Calculations** list, the report warns at the top that it shows today's results.

## Which checklist revision is printed

A checklist report shows the revision you have open, and a **Checklists** list prints the latest one. For an older revision, open it under **Revisions** and click **Print** there.

## Examples

**Who has a copy.** An auditor asks who received the safety checklist. You open its **History**, choose **Distribution** and see two downloads and one print of revision B, each with its date and person.

**A printout found in the hall.** You scan the QR code on its footer. Glados opens the printed revision and tells you that a newer one exists, so you replace the copy.

**Different results today.** An older drive sizing calculation gives different results now. Its page lists the differences and **Print** stays greyed out until you save it again.
