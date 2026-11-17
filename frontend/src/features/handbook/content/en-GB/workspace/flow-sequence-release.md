---
title: Releasing Flow Sequences
summary: How a flow sequence is created or copied, edited one person at a time, released for the PLC programmer, revised and marked invalid.
sourceRefs:
  - backend/src/modules/quality/domain/services/sequence_rules.py
  - backend/src/modules/quality/application/use_cases/sequence/lock_sequence.py
  - backend/src/modules/quality/application/use_cases/sequence/release_sequence.py
  - backend/src/modules/quality/application/use_cases/sequence/revise_sequence.py
  - backend/src/modules/quality/application/use_cases/sequence/delete_sequence.py
  - frontend/src/features/sequences/components/SequenceControls.vue
  - frontend/src/features/sequences/components/SequencesTab.vue
lastVerified: 2026-11-10
---

A flow sequence is a controlled document, like a calculation or a checklist: one person edits a draft at a time, a released revision never changes again, and a correction is a new revision. This page covers what is particular to flow sequences. The rules all three share are on [Editing Documents](/handbook/workspace/document-editing) and [Revisions and Release](/handbook/workspace/document-revisions), and building the steps is on [Flow Sequences](/handbook/workspace/flow-sequences).

## Creating and copying a sequence

**New Sequence** in the **Sequences** tab of a product asks for a name. Pick one of the proposed names, which come from the **Sequence Names** list under Resources, **Product Devices**, or type your own. A right click on a row of the list offers **Copy**, which starts a new draft with the same steps as the revision the list shows. Either way the new draft opens for editing. Both need **Write Flow Sequences**; without it **New Sequence** shows disabled and its tooltip names the permission, and **Copy** shows disabled in the menu and names it when you point at it. An archived product takes no new sequences.

## Editing a draft

A saved sequence opens read only. **Edit** starts editing and holds the draft for you, so nobody else can change it meanwhile. Its creator may edit a draft, and so may anyone with **Manage Flow Sequences**. **Save** keeps your changes and you go on editing. **Done** ends editing and reads **Discard** while there are unsaved changes, and then asks before it throws them away. Unsaved changes stay on this device when you leave, and someone with **Manage Flow Sequences** can take over a draft that was left open. A button you lack the permission for shows disabled, and its tooltip names the permission.

## Releasing

**Release** signs the sequence off, and the PLC programmer works from that revision. It needs **Release Flow Sequences**, and the author may release their own sequence. While you edit, **Release** saves your changes first and ends editing. A sequence without steps cannot be released, and every device, position and variant its steps name must still be in use, so a step that names an archived device has to change first. The release keeps the device names, positions, initial positions and travel times as they are now, so renaming a device later never changes a released sequence.

## New revisions and history

**New Revision** starts the next revision as a draft with the same steps and asks for a reason. The released revision stays valid until the new one is released, and then it reads **Superseded**. **History** lists every revision with its reason, and each one opens. An older revision shows a notice with a link to the latest one.

## Marking a revision invalid

A release cannot be taken back. When a released revision turns out to be wrong, someone with **Manage Flow Sequences** clicks **Mark as Invalid** and gives the reason. The revision stays on record, carries an **Invalid** tag next to its status and shows the reason in a red notice. Correct it in a new revision. **Delete** removes only a draft, after asking first.

## Examples

**A first release.** You build the automatic cycle and click **Release** while still editing. Glados saves the steps, ends editing, and the sequence reads **Released**.

**A correction after commissioning.** Step 4 needs a longer timeout. **New Revision** with the reason "Longer timeout for the gripper" starts a draft, and the PLC programmer keeps working from the released revision until you release the correction.

**A renamed device.** B01 Lift Cylinder P1 becomes B01 Lifting Cylinder P1. The released revision keeps the old name, and the next revision shows the new one.
