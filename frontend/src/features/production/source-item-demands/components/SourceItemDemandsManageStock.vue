<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { extractApiError } from '@/core/utils/errors'
import { useSourceItemDemandsSelectionStore } from '../stores/sourceItemDemandsSelectionStore'
import { useSourceItemDemandsFiltersStore } from '../stores/sourceItemDemandsFiltersStore'
import { useSourceItemsAllocationsStore } from '../stores/sourceItemsAllocationsStore'
import { formatUnit } from '@/shared/utils/units'
import { itemLabel, itemSublabel } from '@/features/source-items'
import EmptyState from '@/shared/components/EmptyState.vue'

defineOptions({ inheritAttrs: false })

const { t } = useI18n()

const selectionStore = useSourceItemDemandsSelectionStore()
const filtersStore = useSourceItemDemandsFiltersStore()
const allocationsStore = useSourceItemsAllocationsStore()

interface StockRow {
  demandId: number
  itemLabel: string
  itemSublabel: string
  projectNumber: string
  unit: string
  quantity: number
  maxQuantity: number
  error: string | null
}

const rows = ref<StockRow[]>([])

// Rebuilt from the selection on every change. Row errors survive, keyed by
// demand id.
function rebuildRows(): void {
  const existingErrors = new Map(rows.value.map((row) => [row.demandId, row.error]))

  rows.value = selectionStore.selectedDemands.map((demand) => {
    const summary = allocationsStore.getSummary(demand.id)
    const max = summary?.unallocated ?? demand.quantity
    return {
      demandId: demand.id,
      itemLabel: itemLabel(demand),
      itemSublabel: itemSublabel(demand),
      projectNumber: demand.project_number,
      unit: demand.unit,
      quantity: max,
      maxQuantity: max,
      error: existingErrors.get(demand.id) ?? null,
    }
  })
}

// selectedDemands is replaced wholesale, so a shallow watch suffices.
watch(() => selectionStore.selectedDemands, rebuildRows, { immediate: true })

function removeRow(demandId: number): void {
  selectionStore.selectedDemands = selectionStore.selectedDemands.filter((d) => d.id !== demandId)
}

const submitting = ref(false)

async function onSubmit(): Promise<void> {
  const toFulfill = rows.value.filter((row) => row.quantity > 0)
  if (toFulfill.length === 0) return

  submitting.value = true

  const results = await Promise.allSettled(
    toFulfill.map((row) => allocationsStore.fulfillFromStock(row.demandId, row.quantity)),
  )

  const failedIds = new Set<number>()
  results.forEach((result, index) => {
    const row = toFulfill[index]
    if (!row) return
    if (result.status === 'rejected') {
      failedIds.add(row.demandId)
      const current = rows.value.find((r) => r.demandId === row.demandId)
      if (current) {
        current.error = extractApiError(result.reason) ?? t('sourceItems.demands.stock.errors.unknown')
      }
    }
  })

  submitting.value = false

  if (failedIds.size === 0) {
    selectionStore.clearSelection()
    selectionStore.triggerRefresh()
    return
  }

  // Partial success keeps only the failed rows selected so they can be
  // retried.
  selectionStore.selectedDemands = selectionStore.selectedDemands.filter((d) => failedIds.has(d.id))
  selectionStore.triggerRefresh()
}
</script>

<template>
  <Panel class="manage-stock-panel fill-panel" v-bind="$attrs">
    <template #header>
      <div class="panel-header-row">
        <span class="panel-title">{{ t('sourceItems.demands.stock.title') }}</span>
        <Tag
          v-if="selectionStore.selectedDemands.length > 0"
          :value="
            t('sourceItems.demands.procure.selectedCount', {
              count: selectionStore.selectedDemands.length,
            })
          "
          severity="secondary"
        />
      </div>
    </template>
    <template #icons>
      <Button
        icon="mdi mdi-close"
        severity="secondary"
        text
        rounded
        size="small"
        :aria-label="t('common.close')"
        @click="filtersStore.closePanel()"
      />
    </template>

    <div class="rows-section">
      <EmptyState v-if="rows.length === 0" :message="t('sourceItems.demands.stock.empty')" icon="mdi mdi-package-variant-closed" />

      <div v-else class="rows-list">
        <div v-for="row in rows" :key="row.demandId" class="row-card">
          <div class="row-item">
            <span class="row-name">{{ row.itemLabel }}</span>
            <span class="row-code">{{ row.itemSublabel }}</span>
            <span class="row-project">{{ row.projectNumber }}</span>
          </div>

          <div class="row-controls">
            <InputNumber
              v-model="row.quantity"
              :min="0"
              :max="row.maxQuantity"
              :max-fraction-digits="3"
              :input-style="{ width: '6rem' }"
              size="small"
            />
            <span class="row-unit">{{ formatUnit(row.unit) }}</span>
            <Button
              icon="mdi mdi-close"
              severity="secondary"
              text
              rounded
              size="small"
              :aria-label="t('common.delete')"
              @click="removeRow(row.demandId)"
            />
          </div>

          <Message v-if="row.error" severity="error" :closable="false" size="small">
            {{ row.error }}
          </Message>
        </div>
      </div>
    </div>

    <div class="panel-footer">
      <Button
        :label="t('sourceItems.demands.stock.fulfillButton', { count: rows.length })"
        icon="mdi mdi-package-variant-closed"
        :disabled="rows.length === 0"
        :loading="submitting"
        fluid
        @click="onSubmit"
      />
    </div>
  </Panel>
</template>

<style scoped lang="scss">
.manage-stock-panel {
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
  padding: var(--space-2) var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.row-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-bottom: var(--space-1);
}

.row-name {
  font-weight: 600;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.row-code,
.row-project {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.row-controls {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.row-unit {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.panel-footer {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
</style>
