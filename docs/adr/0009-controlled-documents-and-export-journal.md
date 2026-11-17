# 0009 controlled documents with revisions, an edit lock and an export journal

- Status: accepted
- Date: 2026-10-20

## context

Calculations and checklists end up in a machine's technical file, where ISO 9001 7.5.3 asks for controlled documents: identified revisions, approval, protection against unintended change, and a record of distribution. Checklists had revisions of their own, calculations had none, and both let a manager withdraw a release and edit the record again. Two users could edit the same draft at once, and nothing recorded which PDF left Glados. Keeping a frozen copy of every exported PDF was considered and dropped: the files would grow without bound and still not say who received them.

## decision

Every such record is a controlled document with one shared mechanism (`domain/entities/controlled_document.py`, `domain/services/document_control.py`, `application/services/controlled_documents.py`): revisions of a lineage numbered with the made item revision settings, exactly one latest revision, a release that never changes again, "mark as invalid" with a reason instead of withdrawing a release, and an edit lock that is a 15 minute lease renewed while editing, which a manager may take over. Every download and print of a saved record's report is written to the export journal with the record, the exact revision, the language, options and versions and the SHA-256 of the file; Glados keeps no copy, since a released revision reproduces the same report. Every page of such a report carries a QR code to `/resolve/{public_id}` of that revision and a line marking it as a copy. Report builders style by name only: the engine owns the named styles, spacing presets and drawing colours, and ESLint keeps raw styling and pdfmake imports out of feature report code.

## consequences

A new kind of document (such as the technical documents of a product's technical file) mixes in the shared columns and fields and gets revisions, release, lock and invalid marking without new rules; the recipe for its report is in [CONTRIBUTING.md section 2.6](../CONTRIBUTING.md#26-add-a-pdf-report). A printed page can always be checked against the current revision, and the distribution list of a record answers who exported what. Only the holder of the edit lock saves a draft, a released revision is never deleted, and the owner keys of the tables restrict instead of cascade. The journal trusts the hash the browser computes for a download; a print's hash is computed by the server from the bytes it sends.
