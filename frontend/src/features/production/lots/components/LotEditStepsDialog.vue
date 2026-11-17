<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { hasAction } from '@/core/utils/lifecycleActions'
import { useAppToast } from '@/core/composables/useAppToast'

import { extractApiError } from '@/core/utils/errors'
import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'
import { useLotStructureDraft } from '../composables/useLotStructureDraft'
import LotStepList from './LotStepList.vue'
import LotPositionGrouping from './LotPositionGrouping.vue'

const props = defineProps<{
  lotId: number | null
  canWrite: boolean
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const toast = useAppToast()
const detailStore = useProductionLotDetailStore()

const lot = computed(() =>
  detailStore.lot && detailStore.lot.id === props.lotId ? detailStore.lot : null,
)

// Editable while the lot offers structure edits, which a completed,
// canceled or scrapped lot does not; assigned positions are guarded per
// field.
const readonly = computed(() => !props.canWrite || !hasAction(lot.value, 'edit_structure'))

const draft = useLotStructureDraft(lot)

watch(visible, (isVisible) => {
  if (isVisible && props.lotId !== null) void detailStore.fetch(props.lotId)
  else if (!isVisible) draft.reset()
})

async function save(): Promise<void> {
  if (props.lotId === null) return
  try {
    // false means the structure saved but a staged pick failed; the dialog stays
    // open so the planner can save again.
    const succeeded = await draft.save(props.lotId)
    if (succeeded) visible.value = false
  } catch (e) {
    toast.error(t('production.lots.editSteps.saveError'), extractApiError(e) ?? undefined)
  }
}

function cancel(): void {
  draft.reset()
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      lot
        ? t('production.lots.editSteps.titleFor', { number: lot.lot_number })
        : t('production.lots.editSteps.title')
    "
    :style="{ width: 'var(--dialog-width-full)' }"
  >
    <div v-if="!lot" class="edit-steps-loading">
      <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
    </div>
    <div v-else class="edit-steps-body">
      <Message v-if="draft.isDirty.value" severity="warn" size="small" :closable="false">
        {{ t('production.lots.editSteps.unsaved') }}
      </Message>

      <LotStepList
        :lot-id="lot.id"
        :steps="draft.draftSteps.value"
        :positions="draft.draftPositions.value"
        :made-item-id="lot.made_item_id"
        :made-item-part-number="lot.made_item_part_number"
        :made-item-revision="lot.made_item_revision"
        :made-item-article-name="lot.made_item_article_name"
        :readonly="readonly"
        :pending-assignments="draft.pendingAssignments.value"
        :pending-reassignments="draft.pendingReassignments.value"
        staged
        @edit-step="draft.editStep"
        @remove-step="draft.removeStep"
        @append-step="draft.appendStep"
        @reorder-positions="draft.reorderPositions"
        @assign-position="draft.assignPosition"
        @clear-assignment="draft.clearAssignment"
        @reassign-order="draft.reassignOrder"
        @clear-reassignment="draft.clearReassignment"
      />

      <Divider />

      <!-- Adding a step always appends a position, so grouping must be reachable
           wherever steps are editable. -->
      <LotPositionGrouping
        :lot-id="lot.id"
        :steps="draft.draftSteps.value"
        :positions="draft.draftPositions.value"
        :readonly="readonly"
        staged
        @regroup="draft.regroup"
      />
    </div>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="draft.saving.value"
        @click="cancel"
      />
      <Button
        :label="t('common.save')"
        :loading="draft.saving.value"
        :disabled="readonly || !draft.isDirty.value"
        @click="save"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.edit-steps-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.edit-steps-loading {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
  font-size: var(--font-size-2xl);
  color: var(--p-text-muted-color);
}
</style>
