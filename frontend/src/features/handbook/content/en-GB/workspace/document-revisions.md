---
title: Revisions and Release
summary: How calculations, checklists and flow sequences get their document number and revisions, are released for good, marked invalid and found in the lists.
sourceRefs:
  - backend/src/modules/quality/domain/entities/controlled_document.py
  - backend/src/modules/quality/application/services/controlled_documents.py
  - backend/src/modules/platform/adapters/outbound/persistence/number_counters.py
  - backend/src/modules/quality/domain/services/calculation_rules.py
  - backend/src/modules/quality/domain/services/checklist_rules.py
  - backend/src/modules/quality/domain/services/sequence_rules.py
  - frontend/src/shared/documents/utils/rowMenu.ts
lastVerified: 2026-11-10
---

Calculations, checklists and flow sequences are controlled documents: a released revision never changes again, and a correction is a new revision. A product shows them in its **Calculations**, **Checklists** and **Sequences** tabs, and a project in its **Calculations** and **Checklists** tabs. How a draft is edited is on [Editing Documents](/handbook/workspace/document-editing), and what is particular to flow sequences is on [Releasing Flow Sequences](/handbook/workspace/flow-sequence-release).

## Document numbers

Every document gets a number when it is first saved, for example CAL-26-0042 for a calculation, CHK-26-0017 for a checklist or SEQ-26-0003 for a flow sequence. All revisions of the document share it, so CAL-26-0042 rev. B names exactly one revision. The number appears in the info bar, the lists and every report, and the search finds it. Administrators set the formats under Settings, **Numbering**. A changed format applies to new documents only.

## Revisions

The revisions are counted the way the settings count made item revisions, for example 0, 1, 2 or A, B, C. A revision that is not released yet shows as B (draft). **New Revision** continues a released document: the new revision starts as a draft with the same content and the reason you give. The released revision stays the valid one until the new revision is released, and then it is superseded. An older revision shows a notice with a link to the latest one. **Save as New** in a calculation is different, because it starts an independent calculation with its own number and revisions.

## Releasing

Releasing signs a revision off. It never changes again and is never deleted, also not by administrators; only drafts can be deleted. A calculation and a flow sequence may be released by their author, with **Release Calculations** or **Release Flow Sequences**. A checklist whose type needs a release needs a second person with **Release Checklists**, because whoever created a revision never releases it. Without the permission **Release** shows disabled, and its tooltip names it.

## Marking a revision invalid

A release cannot be taken back. If a released revision turns out to be wrong, a user with the manage permission of its kind, such as **Manage Calculations**, clicks **Mark as Invalid** and gives the reason. The revision stays on record, shows a red notice with the reason, and every report of it carries a warning. Correct it in a new revision. When a revision is marked invalid or a new revision is started, everyone who created or saved a revision of the document is notified.

## In the lists

The lists show each document's revision, who released it and when, whether it was marked invalid, and a lock while someone is editing it. A right click on a row opens its menu: open it, also in a new tab, copy its link, print it where it has a report, and the steps of the document itself, such as **Edit**, **History**, **New Revision**, **Release** and **Mark as Invalid**. These open the document and start the step there. **Delete** is offered for drafts only. A step the document allows but you may not take shows disabled, and pointing at it names the permission you lack or who is editing the document.

## Printed copies

Every report of a saved calculation or checklist carries a QR code that opens exactly that revision, so a reader with a printout can always check whether it is still valid. See [Exporting and Printing Reports](/handbook/resources/report-export).

## Examples

**A checklist signed off.** The designer fills in the CE checklist and asks the safety engineer to release it. The designer cannot release it, because they created that revision.

**A wrong value found later.** A released drive sizing used the wrong load. A manager marks CAL-26-0042 rev. A invalid, and the designer corrects the load in rev. B.
