---
title: Editing Documents
summary: How calculations, checklists and flow sequences are edited one person at a time, how unsaved changes are kept, and how a draft left open is taken over.
sourceRefs:
  - backend/src/modules/quality/domain/entities/controlled_document.py
  - backend/src/modules/quality/domain/services/document_control.py
  - frontend/src/shared/documents/composables/useDocumentLock.ts
  - frontend/src/shared/documents/composables/useLocalDraft.ts
  - frontend/src/shared/composables/useLeaveGuard.ts
  - frontend/src/features/tools/components/ToolCalculationControls.vue
  - frontend/src/features/checklists/components/ChecklistControls.vue
  - frontend/src/features/sequences/components/SequenceControls.vue
lastVerified: 2026-11-10
---

Calculations, checklists and flow sequences are documents that can end up in a machine's technical file, so they are edited the same way: one person edits a draft at a time, and nothing you typed is lost while you work. You open them from the tabs of a product or project. How they are numbered, released and revised is on [Revisions and Release](/handbook/workspace/document-revisions).

## Editing a draft

A saved draft opens read only. Click **Edit** to start changing it. A draft is edited by the person who created it, or by someone with the manage permission of its kind, such as **Manage Checklists**. Without the permission **Edit** shows disabled, and its tooltip names what is missing. From then on you hold the draft: others see a notice with your name and since when you are editing, and they cannot save, release or edit it until you finish.

**Save** stores your changes in the draft and keeps you editing. **Done** ends editing; while there are unsaved changes it reads **Discard** and asks before it throws them away. **Release** also works while you edit: it saves your changes first and ends editing. Leaving the page ends editing too.

If nobody works on the page for about 13 minutes, editing ends by itself and the draft is free again, so a page left open overnight blocks nobody. If you close the browser while editing, the draft is free again after 15 minutes.

In a calculation tool you can try other inputs without **Edit**. Such figures are only on your screen, and **Save** keeps them as a new calculation. A tool without a saved calculation remembers its inputs on this device, also when you switch tabs or reload, until **New** clears them or **Save** turns them into a calculation.

## Unsaved changes

Unsaved changes are kept on this device while you work, so nothing is lost when you leave the page, reload it, close the browser, your session runs out or someone takes over. Leaving the page with unsaved changes asks first.

When you open the document again, Glados offers the changes with the time you made them. **Restore** puts them back and starts editing, **Discard** drops them, and closing the dialog keeps them for later. If someone saved the document in the meantime, the dialog warns that restoring puts your changes over the newer version. Kept changes are offered only to you and stay until you save or discard them, also when you sign out. Changes nobody came back to are dropped after ten weeks.

## Taking over

When someone left a draft open and is not around, a user with **Manage Calculations**, **Manage Checklists** or **Manage Flow Sequences** can click **Take over** in the notice to edit it themselves, or **End editing** to free the draft for anyone. The other person is notified, and their unsaved changes stay only on their device.

## Examples

**A long phone call.** You leave a checklist open while editing. After about 13 minutes editing ends and your answers stay on this device. Glados offers them again, and **Restore** puts them back.

**A colleague on holiday.** A draft calculation shows that a colleague has been editing it since Monday. Someone with **Manage Calculations** clicks **Take over** and goes on with the draft.
