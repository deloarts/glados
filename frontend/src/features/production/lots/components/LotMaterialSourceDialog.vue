<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { HelpDrawer } from '@/shared/help'

import { apiErrorStatus, extractApiError } from '@/core/utils/errors'
import { MaterialSourceSelect } from '@/features/made-items'
import { getSourceItemDemandSummaryBatch } from '@/features/source-items'
import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { useConfirmAsync } from '@/shared/composables/useConfirmAsync'
import { MadeItemThumbnailCell } from '@/features/made-items'
import { useMadeItemDetail } from '@/features/made-items'
import { useMadeItemLabel } from '@/features/made-items'
import { switchLotMaterialSource } from '../api/switchLotMaterialSource'

import type { MaterialSource } from '@/features/made-items'
import type { LotResponse } from '../../types/productionLotsResponse'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useErrorToast } from '@/core/composables/useErrorToast'

const props = defineProps<{
  lotId: number | null
  madeItemId: number | null
  currentSource: MaterialSource
  currentDemandStatus?: string | null
  // The lot's raw material demand and edit version, which the switch sends
  // so a lot changed since the view loaded it answers 409.
  inputDemandId?: number | null
  editVersion?: number | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  updated: [lot: LotResponse]
  // The server refused the switch with a 409 because the lot changed since
  // the view loaded it, so the view reloads the lot.
  conflict: []
}>()

const { t } = useI18n()
// Opens the handbook page that explains this dialog.
const explainVisible = ref(false)
const { toastOnError } = useErrorToast()
const { ask } = useConfirmAsync()
const { formatNumber } = useLocaleFormat()

const source = ref<MaterialSource>({
  bought_item_id: null,
  source_item_id: null,
  made_item_id: null,
})

const submitting = ref(false)
const errorMessage = ref<string | null>(null)

const { detailItem: madeItem, openDetailById } = useMadeItemDetail()
const { format: madeItemLabel } = useMadeItemLabel()

const materialSourceRef = ref<InstanceType<typeof MaterialSourceSelect> | null>(null)
const saveLabel = computed(() => materialSourceRef.value?.submitLabel ?? t('common.save'))

watch(visible, (isVisible) => {
  if (!isVisible) return
  source.value = { ...props.currentSource }
  errorMessage.value = null
  if (props.madeItemId !== null) openDetailById(props.madeItemId).catch(toastOnError())
})

async function submit(confirmReplaceDemand: boolean): Promise<void> {
  if (!props.lotId) return

  submitting.value = true
  errorMessage.value = null

  try {
    const updated = await switchLotMaterialSource(props.lotId, {
      ...source.value,
      confirm_replace_demand: confirmReplaceDemand,
      expected_edit_version: props.editVersion ?? 0,
    })
    visible.value = false
    emit('updated', updated)
  } catch (e) {
    errorMessage.value =
      extractApiError(e) ?? t('production.lots.detail.materialSource.errors.unknown')
    if (apiErrorStatus(e) === 409) emit('conflict')
  } finally {
    submitting.value = false
  }
}

async function onSubmit(): Promise<void> {
  // A no-op passthrough for the three "choose existing" modes; in "Create
  // Source Item" mode this actually creates the item first and folds its id
  // into `source` before the switch below runs.
  submitting.value = true
  const resolved = await materialSourceRef.value?.resolve()
  submitting.value = false
  if (!resolved) return

  if (props.currentDemandStatus === 'open') {
    const go = await ask({
      message: t('production.lots.detail.materialSource.confirmReplace.message'),
      header: t('production.lots.detail.materialSource.confirmReplace.header'),
      icon: 'mdi mdi-alert',
      rejectProps: { label: t('common.cancel'), severity: 'secondary' },
      acceptProps: {
        label: t('production.lots.detail.materialSource.confirmReplace.accept'),
        severity: 'danger',
      },
    })
    if (go) await submit(true)
    return
  }
  if (isPlaced(props.currentDemandStatus) && props.inputDemandId) {
    const message = await placedDemandMessage(props.inputDemandId)
    if (message === null) return
    const go = await ask({
      message,
      header: t('production.lots.detail.materialSource.confirmPlaced.header'),
      icon: 'mdi mdi-alert',
      rejectProps: { label: t('common.cancel'), severity: 'secondary' },
      acceptProps: {
        label: t('production.lots.detail.materialSource.confirmPlaced.accept'),
        severity: 'danger',
      },
    })
    if (go) await submit(true)
    return
  }
  await submit(false)
}

// A demand already allocated or ordered is replaced only after the user saw
// what arrived: that stays with the lot, the rest is demanded anew.
function isPlaced(status: string | null | undefined): boolean {
  return status === 'allocated' || status === 'ordered'
}

async function placedDemandMessage(demandId: number): Promise<string | null> {
  submitting.value = true
  try {
    const summary = (await getSourceItemDemandSummaryBatch([demandId]))[demandId]
    if (!summary) return null
    const arrived = summary.delivered + summary.fulfilled_from_stock
    return t('production.lots.detail.materialSource.confirmPlaced.message', {
      ordered: formatNumber(summary.allocated),
      arrived: formatNumber(arrived),
      missing: formatNumber(Math.max(summary.total - arrived, 0)),
      unit: summary.unit,
    })
  } catch (e) {
    errorMessage.value =
      extractApiError(e) ?? t('production.lots.detail.materialSource.errors.unknown')
    return null
  } finally {
    submitting.value = false
  }
}

function onCancel(): void {
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <template #header>
      <div class="material-source-header">
        <span class="p-dialog-title">{{ t('production.lots.detail.materialSource.title') }}</span>
        <Button
          type="button"
          class="material-source-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('production.lots.detail.materialSource.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('production.lots.detail.materialSource.explain')"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <div class="dialog-body">
      <div v-if="madeItem" class="made-item-info">
        <MadeItemThumbnailCell
          :item-id="madeItem.id"
          :item-name="madeItem.article_name"
          size="4rem"
          no-image-icon="mdi mdi-image-off-outline"
        />
        <div class="made-item-fields">
          <div class="made-item-field">
            <span class="form-label">{{ t('madeItems.create.fields.partNumber') }}</span>
            <span class="field-value">{{ madeItemLabel(madeItem.part_number, madeItem.revision) }}</span>
          </div>
          <div class="made-item-field">
            <span class="form-label">{{ t('madeItems.create.fields.articleName') }}</span>
            <span class="field-value">{{ madeItem.article_name }}</span>
          </div>
          <div class="made-item-field">
            <span class="form-label">{{ t('madeItems.create.fields.baseSize') }}</span>
            <span class="field-value">{{ madeItem.base_size || getEmptyPlaceholder() }}</span>
          </div>
          <div class="made-item-field">
            <span class="form-label">{{ t('madeItems.create.fields.material') }}</span>
            <span class="field-value">{{ madeItem.material || getEmptyPlaceholder() }}</span>
          </div>
          <div class="made-item-field made-item-field-note">
            <span class="form-label">{{ t('madeItems.create.fields.note') }}</span>
            <span class="field-value">{{ madeItem.note || getEmptyPlaceholder() }}</span>
          </div>
        </div>
      </div>

      <MaterialSourceSelect
        ref="materialSourceRef"
        v-model="source"
        :allow-made="true"
        :allow-create="true"
      />

      <Message v-if="errorMessage" severity="error" :closable="false">
        {{ errorMessage }}
      </Message>
    </div>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="submitting"
        @click="onCancel"
      />
      <Button :label="saveLabel" :loading="submitting" @click="onSubmit" />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="production/material-source" anchor="change" />
</template>

<style scoped lang="scss">
.material-source-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.material-source-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.dialog-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding-top: var(--space-1);
}

.made-item-info {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-sm);
  background: var(--p-content-hover-background);
}

.made-item-fields {
  flex: 1;
  min-width: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-1) var(--space-4);
}

.made-item-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.made-item-field-note {
  grid-column: 1 / -1;
}

.form-label {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.field-value {
  font-size: var(--font-size-sm);
  font-weight: 500;
  overflow-wrap: anywhere;
}
</style>
