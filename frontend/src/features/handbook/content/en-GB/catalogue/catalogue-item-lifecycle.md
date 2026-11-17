---
title: Catalogue Item Lifecycle
summary: What Active, Inactive and Replaced mean for a bought, made or source item, how you move an item between them, and what a successor does.
sourceRefs:
  - backend/src/modules/catalogue/domain/policies/catalogue_item_status.py
  - backend/src/modules/catalogue/domain/policies/pdm_ownership.py
  - backend/src/read/domain/services/state_machine_catalog.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

Every bought item, made item and source item has one of three statuses, and the three catalogues share the same rules. Nothing works the status out for you: it says whether the item may still be used for new work. The diagram below is read live from the rules the system runs.

<StateMachineEmbed machine-key="catalogue_item_status" />

## What each status means

**Active** is the normal case. A new demand, lot, order line or substitute may name an item only while it is active, not archived and, for an item from PDM, not **Missing From Vault**. **Inactive** keeps the item in the catalogue but takes it out of new work. **Replaced** does the same and names a **Successor Item** that takes its place. When you pick a replaced item for a new demand, the dialog says "The item you selected is replaced by another item." and offers **Use replacement**. Work that already names an item carries on whatever its status becomes, so changing a status never stops a running lot or an open order line.

## Changing the status

You change the status with **Status** in the item's edit dialog, which needs the write permission of that catalogue, for example **Write Bought Items**. A move to **Replaced** needs a **Successor Item** from the same catalogue that exists, is not archived and does not lead back to the item. A move to **Active** or **Inactive** drops the successor. On an older revision of a made item only the status can change, and **New Revision** sets the status of the current revision for you.

On an item from PDM the status follows the workflow state of its file, so the field is locked and says "Status is managed by PDM. Move the file to a replaced state in PDM before assigning a successor." The successor itself stays yours to set once PDM has marked the item replaced.

Archiving is separate from the status. **Archive** hides the item from the lists, **Restore** brings it back, and **Merge** archives the item it merges away.

## Examples

**A part is discontinued.** The maker stops a relay. You set it to **Inactive**, and nobody can demand it any more, while the open order for it is still delivered.

**A newer part replaces it.** You set the old relay to **Replaced** and pick the new one as **Successor Item**. A colleague who picks the old relay for a demand is offered **Use replacement**.

**A part from PDM.** The engineer moves the file to a replaced state in PDM. After the next sync the item reads **Replaced**, and you pick its successor in the edit dialog.
