# 0007 PDF reports are rendered in the browser and printed as uploaded PDFs

- Status: accepted
- Date: 2026-10-09

## context

Calculations and checklists were printed with the browser's print dialog from special print pages. The result depended on the browser, the user's theme and print settings, broke pages in unpredictable places, and could not be sent to the office printers Glados already drives. The results these documents show are calculated in the frontend (the tool engines, the checklist evaluation), so a server-side renderer would have needed a second copy of every engine, or the frontend would have had to send its results to the server anyway. The existing server renderer draws label and docket images with Pillow and suits neither multi-page text nor charts.

## decision

Reports are built in the browser with pdfmake from a feature's `ReportSpec` and the shared frame in `frontend/src/shared/reports`: a fixed palette independent of the app theme, bundled fonts, the company's logo and name, and PDF/A-2b (ISO 19005-2) as the archival format with the document's language, title and author in its metadata. The export dialog picks the report's language and options, downloads the PDF, or uploads it to `POST /print/document`, which checks that the user may see the record it belongs to, accepts only a PDF, sends it unchanged to an IPP document printer and logs a print job. The browser print pages were removed; a print is always a report of a saved record, an unsaved one can only be downloaded.

## consequences

A report looks the same for every user and on every printer, and is fit for a technical file. Adding a report means writing its body from the shared blocks and, to make it printable, one document kind with its visibility check on the server; the recipe is in [CONTRIBUTING.md section 2.6](../CONTRIBUTING.md#26-add-a-pdf-report). pdfmake and the fonts load on the first export only. Drawings reach a report as SVG, and pdfmake's SVG renderer sets a small gap before every subscript. The server prints exactly what the browser rendered, so it trusts the content of an upload and guards only who may print what.
