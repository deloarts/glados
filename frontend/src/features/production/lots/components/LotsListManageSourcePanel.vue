<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { extractApiError } from '@/core/utils/errors'
import { canSwitchMaterialSource } from '../utils/lotSourceEligibility'
import { MaterialSourceSelect } from '@/features/made-items'
import { HelpButton } from '@/shared/help'
import { switchLotMaterialSource } from '../api/switchLotMaterialSource'
import { useProductionLotsStore } from '../../stores/productionLotsStore'
import { useProductionLotsSourceStore } from '../stores/productionLotsSourceStore'

import type { MaterialSource } from '@/features/made-items'
import type { LotSummaryResponse } from '../../types/productionLotsResponse'
import EmptyState from '@/shared/components/EmptyState.vue'

defineOptions({ inheritAttrs: false })

const emit = defineEmits<{
  assigned: []
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const confirm = useConfirm()
const lotsStore = useProductionLotsStore()
const sourceStore = useProductionLotsSourceStore()

const source = ref<MaterialSource>({
  bought_item_id: null,
  source_item_id: null,
  made_item_id: null,
})

const materialSourceRef = ref<InstanceType<typeof MaterialSourceSelect> | null>(null)
const hasSource = computed(() => materialSourceRef.value?.hasSelection ?? false)
const confirmLabel = computed(
  () => materialSourceRef.value?.submitLabel ?? t('production.lots.manageSource.confirm'),
)

// An open demand is canceled and a placed one keeps what arrived, so both
// are replaced only once the user confirmed it.
function needsDemandConfirm(lot: LotSummaryResponse): boolean {
  return Boolean(lot.input_demand_id) && lot.demand_status !== 'fulfilled'
}

// A finished lot no longer offers a source switch, and one whose material
// has all arrived has nothing left to switch, so the batch skips both
// instead of collecting a refusal for every one.
function isSwitchable(lot: LotSummaryResponse): boolean {
  return canSwitchMaterialSource(lot)
}

const switchableLots = computed(() => sourceStore.selectedLots.filter(isSwitchable))
const skippedCount = computed(
  () => sourceStore.selectedLots.length - switchableLots.value.length,
)

// ── Submit ───────────────────────────────────────────────────────────

const submitting = ref(false)
const errorMessage = ref<string | null>(null)

async function submit(confirmReplaceDemand: boolean): Promise<void> {
  submitting.value = true
  errorMessage.value = null
  const failedLabels: string[] = []
  let anySucceeded = false

  for (const lot of switchableLots.value) {
    try {
      await switchLotMaterialSource(lot.id, {
        ...source.value,
        confirm_replace_demand: confirmReplaceDemand,
        expected_edit_version: lot.edit_version,
      })
      sourceStore.removeLot(lot.id)
      anySucceeded = true
    } catch (e) {
      failedLabels.push(lot.lot_number)
      errorMessage.value = extractApiError(e) ?? t('production.lots.manageSource.errors.unknown')
    }
  }

  submitting.value = false
  if (anySucceeded) lotsStore.triggerRefresh()
  if (failedLabels.length > 0) {
    errorMessage.value = t('production.lots.listManage.batchError', {
      items: failedLabels.join(', '),
    })
  } else {
    emit('assigned')
  }
}

async function onSubmit(): Promise<void> {
  if (!hasSource.value || switchableLots.value.length === 0) return

  // A no-op passthrough for the three "choose existing" modes; in "Create
  // Source Item" mode this actually creates the item first (once, not once
  // per lot) and folds its id into `source` before the loop above runs.
  submitting.value = true
  const resolved = await materialSourceRef.value?.resolve()
  submitting.value = false
  if (!resolved) return

  const lotsNeedingConfirm = switchableLots.value.filter(needsDemandConfirm)
  if (lotsNeedingConfirm.length > 0) {
    confirm.require({
      message: t('production.lots.manageSource.confirmReplace.message', {
        lots: lotsNeedingConfirm.map((lot) => lot.lot_number).join(', '),
      }),
      header: t('production.lots.manageSource.confirmReplace.header'),
      icon: 'mdi mdi-alert',
      rejectProps: { label: t('common.cancel'), severity: 'secondary' },
      acceptProps: {
        label: t('production.lots.manageSource.confirmReplace.accept'),
        severity: 'danger',
      },
      accept: () => void submit(true),
    })
    return
  }
  await submit(false)
}

function onClear(): void {
  sourceStore.clearSelection()
}
</script>

<template>
  <Panel class="manage-source-panel fill-panel" v-bind="$attrs">
    <template #header>
      <div class="panel-header-row">
        <div class="panel-header-main">
          <span class="panel-title">{{ t('production.lots.manageSource.title') }}</span>
          <Tag
            v-if="sourceStore.selectedLots.length > 0"
            :value="
              t('production.lots.listManage.selectedCount', {
                count: sourceStore.selectedLots.length,
              })
            "
            severity="secondary"
          />
        </div>
        <HelpButton slug="production/material-source" size="small" rounded />
      </div>
    </template>

    <div class="source-section">
      <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- the source picker is a group of controls, the label names it through aria-labelledby -->
      <label :id="`${uid}-source`" class="field-label">{{ t('production.lots.manageSource.selectSource') }}</label>
      <MaterialSourceSelect
        ref="materialSourceRef"
        v-model="source"
        role="group"
        :aria-labelledby="`${uid}-source`"
        allow-made
        allow-create
      />
    </div>

    <EmptyState v-if="sourceStore.selectedLots.length === 0" :message="t('production.lots.listManage.selectLotPrompt')" icon="mdi mdi-cursor-default-click-outline" />

    <div v-else class="rows-section">
      <div class="rows-list">
        <div
          v-for="lot in sourceStore.selectedLots"
          :key="lot.id"
          class="row-card"
          :class="{ 'row-card--skipped': !isSwitchable(lot) }"
          :data-testid="isSwitchable(lot) ? undefined : 'manage-source-skipped'"
        >
          <div class="row-header row-header--static">
            <span class="row-seq">{{ lot.lot_number }}</span>
            <div class="row-current-source">
              <span class="row-current-source-label">{{ lot.source_label }}</span>
              <span v-if="lot.source_sublabel" class="row-current-source-sublabel">{{
                lot.source_sublabel
              }}</span>
            </div>
            <i
              v-if="!isSwitchable(lot)"
              class="mdi mdi-cancel row-skipped-icon"
              aria-hidden="true"
              v-tooltip="t('production.lots.manageSource.skippedHint')"
            />
            <i
              v-else-if="needsDemandConfirm(lot)"
              class="mdi mdi-alert row-warning-icon"
              aria-hidden="true"
              v-tooltip="t('production.lots.manageSource.openDemandHint')"
            />
            <Button
              icon="mdi mdi-close"
              severity="secondary"
              text
              rounded
              size="small"
              :aria-label="t('production.lots.listManage.removeFromSelection')"
              @click="sourceStore.removeLot(lot.id)"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="panel-footer">
      <Message
        v-if="skippedCount > 0"
        severity="secondary"
        :closable="false"
        size="small"
        data-testid="manage-source-skipped-count"
      >
        {{ t('production.lots.manageSource.skippedCount', { count: skippedCount }, skippedCount) }}
      </Message>
      <Message
        v-if="errorMessage"
        severity="error"
        :closable="false"
        size="small"
        data-testid="manage-source-error"
      >
        {{ errorMessage }}
      </Message>
      <Button
        :label="confirmLabel"
        icon="mdi mdi-database-import-outline"
        :disabled="!hasSource || switchableLots.length === 0"
        :loading="submitting"
        fluid
        @click="onSubmit"
      />
      <Button
        v-if="sourceStore.selectedLots.length > 0 || hasSource"
        :label="t('production.lots.listManage.clearSelection')"
        severity="secondary"
        outlined
        size="small"
        fluid
        @click="onClear"
      />
    </div>
  </Panel>
</template>

<style scoped lang="scss">
.manage-source-panel {
  flex: 0 0 auto;
  --fill-panel-gap: var(--space-3);
}

.panel-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: var(--space-2);
}

.panel-header-main {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.source-section {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.field-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
}



.rows-section {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.rows-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.row-card {
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  display: flex;
  flex-direction: column;
}

.row-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-2);
}

.row-header--static {
  cursor: default;
}

.row-seq {
  font-weight: 700;
  font-size: var(--font-size-sm);
  white-space: nowrap;
}

.row-current-source {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.row-current-source-label {
  font-size: var(--font-size-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-current-source-sublabel {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.row-warning-icon {
  color: var(--p-orange-500);
  flex-shrink: 0;
}

.row-card--skipped {
  opacity: 0.6;
}

.row-skipped-icon {
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}

.panel-footer {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
</style>
