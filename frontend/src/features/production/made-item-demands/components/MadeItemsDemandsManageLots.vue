<script setup lang="ts">
import { ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { roundTo } from '@/core/utils/numbers'
import { dateToParam, earlierDate, toLocalDayStart } from '@/core/utils/dates'
import { useMadeItemsProcurementStore } from '../stores/madeItemsProcurementStore'
import { useMadeItemsAllocationsStore } from '../stores/madeItemsAllocationsStore'
import { useProductionLotsStore } from '../../stores/productionLotsStore'
import { LOT_PRIORITIES } from '../../utils/lotStatus'

import type { LotPriority } from '../../types/productionLotsResponse'
import type { ProjectRef } from '@/core/types/projectRef'
import { useMadeItemsDemandsStore, useMadeItemLabel } from '@/features/made-items'
import EmptyState from '@/shared/components/EmptyState.vue'

defineOptions({ inheritAttrs: false })

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()

const procurementStore = useMadeItemsProcurementStore()
const allocationsStore = useMadeItemsAllocationsStore()
const demandsStore = useMadeItemsDemandsStore()
const lotsStore = useProductionLotsStore()
const { format: madeItemLabel } = useMadeItemLabel()

interface RowDemand {
  id: number
  quantity: number
  // The demand's unallocated amount, which caps this row and is restored when
  // the lot quantity rises again.
  maxQuantity: number
}

// eslint-disable-next-line no-restricted-syntax -- editable table row state aggregated from several demands
interface EditableRow {
  made_item_id: number
  item_part_number: string
  item_revision: string
  item_article_name: string
  project: ProjectRef
  quantity: number
  priority: LotPriority
  requiredDeliveryDate: Date | null
  demands: RowDemand[]
}

const editableRows = ref<EditableRow[]>([])

/**
 * Allocations can never exceed the lot quantity, so lowering it walks the
 * allocations down: demands fill in row order up to their ceilings until the
 * quantity runs out. Raising it refills them the same way.
 */
function distributeToDemands(row: EditableRow): void {
  let remaining = Math.max(row.quantity, 0)
  for (const demand of row.demands) {
    const share = Math.min(demand.maxQuantity, remaining)
    demand.quantity = roundTo(share, 6)
    remaining = roundTo(remaining - share, 6)
  }
}

function setLotQuantity(row: EditableRow, value: number | null): void {
  row.quantity = value ?? 0
  distributeToDemands(row)
}

/**
 * Allocating more than the lot produces grows the lot. Each demand still
 * stops at its unallocated remainder.
 */
function setDemandQuantity(row: EditableRow, demand: RowDemand, value: number | null): void {
  demand.quantity = Math.min(Math.max(value ?? 0, 0), demand.maxQuantity)
  const allocated = roundTo(row.demands.reduce((sum, d) => sum + d.quantity, 0), 6)
  if (allocated > row.quantity) row.quantity = allocated
}

const globalPriority = ref<LotPriority | null>(null)
const globalRequiredDeliveryDate = ref<Date | null>(null)

function applyGlobalOverwrites(): void {
  if (globalPriority.value) {
    for (const row of editableRows.value) row.priority = globalPriority.value
  }
  if (globalRequiredDeliveryDate.value) {
    for (const row of editableRows.value)
      row.requiredDeliveryDate = globalRequiredDeliveryDate.value
  }
}

function rebuildRows(): void {
  const map = new Map<string, EditableRow>()

  for (const d of procurementStore.selectedDemands) {
    const effectiveQty = allocationsStore.getSummary(d.id)?.unallocated ?? d.quantity
    const key = `${d.made_item_id}|${d.project_id}`
    // The row snapshot can go stale, so the live demand's date wins.
    const liveDemand = demandsStore.items.find((item) => item.id === d.id)
    const desiredDate = liveDemand?.desired_delivery_date ?? d.desired_delivery_date
    const demandDate = desiredDate ? toLocalDayStart(desiredDate) : null
    if (map.has(key)) {
      const row = map.get(key)!
      row.quantity = roundTo(row.quantity + effectiveQty, 6)
      row.demands.push({ id: d.id, quantity: effectiveQty, maxQuantity: effectiveQty })
      if (d.high_priority) row.priority = 'high'
      row.requiredDeliveryDate = earlierDate(row.requiredDeliveryDate, demandDate)
    } else {
      map.set(key, {
        made_item_id: d.made_item_id,
        item_part_number: d.item_part_number,
        item_revision: d.item_revision,
        item_article_name: d.item_article_name,
        project: {
          id: d.project_id,
          project_number: d.project_number,
          customer: { name: d.project_customer },
          description: null,
        },
        quantity: effectiveQty,
        priority: d.high_priority ? 'high' : 'normal',
        requiredDeliveryDate: demandDate,
        demands: [{ id: d.id, quantity: effectiveQty, maxQuantity: effectiveQty }],
      })
    }
  }

  editableRows.value = [...map.values()]
  applyGlobalOverwrites()
}

// selectedDemands is replaced wholesale, so a shallow watch suffices.
watch(
  () => procurementStore.selectedDemands,
  () => rebuildRows(),
)

function removeDemand(demandId: number): void {
  procurementStore.selectedDemands = procurementStore.selectedDemands.filter(
    (d) => d.id !== demandId,
  )
}

const priorityOptions = LOT_PRIORITIES.map((p) => ({ value: p, label: p }))

const { submitting, errorMessage, run } = useSubmitAction()

async function onSubmit(): Promise<void> {
  const rows = editableRows.value.filter(
    (row) => row.quantity > 0 && row.demands.some((d) => d.quantity > 0),
  )
  if (rows.length === 0) return

  await run(async () => {
    for (const row of rows) {
      await lotsStore.create({
        made_item_id: row.made_item_id,
        project_id: row.project.id,
        quantity: row.quantity,
        priority: row.priority,
        required_delivery_date: dateToParam(row.requiredDeliveryDate),
        demand_allocations: row.demands
          .filter((d) => d.quantity > 0)
          .map((d) => ({ demand_item_id: d.id, quantity: d.quantity })),
      })
    }
    procurementStore.clearSelection()
    procurementStore.triggerRefresh()
  }, t('madeItems.demands.manageLots.errors.unknown'))
}
</script>

<template>
  <Panel class="manage-lots-panel fill-panel" v-bind="$attrs">
    <template #header>
      <div class="panel-header-row">
        <span class="panel-title">{{ t('madeItems.demands.manageLots.title') }}</span>
        <Tag
          v-if="procurementStore.selectedDemands.length > 0"
          :value="
            t('madeItems.demands.manageLots.selectedCount', {
              count: procurementStore.selectedDemands.length,
            })
          "
          severity="secondary"
        />
      </div>
    </template>

    <div v-if="editableRows.length > 0" class="global-overwrite">
      <label :id="`${uid}-overwrite-priority-label`" :for="`${uid}-overwrite-priority`" class="field-label">
        {{ t('madeItems.demands.manageLots.overwritePriority') }}
      </label>
      <Select
        v-model="globalPriority"
        :input-id="`${uid}-overwrite-priority`"
        :aria-labelledby="`${uid}-overwrite-priority-label`"
        :options="priorityOptions"
        option-label="label"
        option-value="value"
        :placeholder="t('madeItems.demands.manageLots.overwritePlaceholder')"
        show-clear
        size="small"
        fluid
        @update:model-value="applyGlobalOverwrites"
      />

      <label :for="`${uid}-overwrite-required-delivery-date`" class="field-label">{{
        t('madeItems.demands.manageLots.overwriteRequiredDeliveryDate')
      }}</label>
      <DatePicker
        v-model="globalRequiredDeliveryDate"
        :input-id="`${uid}-overwrite-required-delivery-date`"
        show-button-bar
        show-clear
        size="small"
        fluid
        @update:model-value="applyGlobalOverwrites"
      />
    </div>

    <div class="rows-section">
      <EmptyState v-if="editableRows.length === 0" :message="t('madeItems.demands.manageLots.noSelection')" icon="mdi mdi-checkbox-marked-outline" />

      <div v-else class="rows-list">
        <div
          v-for="row in editableRows"
          :key="`${row.made_item_id}|${row.project.id}`"
          class="row-card"
          :class="{ 'row-card--zero-qty': row.quantity <= 0 }"
        >
          <i
            v-if="row.quantity <= 0"
            class="mdi mdi-alert zero-qty-badge"
            v-tooltip.left="t('madeItems.demands.manageLots.zeroQuantityWarning')"
            aria-hidden="true"
          />

          <div class="row-item">
            <span class="row-name">{{ row.item_article_name }}</span>
            <span class="row-code">{{ madeItemLabel(row.item_part_number, row.item_revision) }}</span>
            <span class="row-project">{{ row.project.project_number }}</span>
          </div>

          <div class="row-controls">
            <label :for="`${uid}-lot-quantity-${row.made_item_id}-${row.project.id}`" class="field-label">
              {{ t('madeItems.demands.manageLots.lotQuantity') }}
            </label>
            <InputNumber
              :input-id="`${uid}-lot-quantity-${row.made_item_id}-${row.project.id}`"
              :model-value="row.quantity"
              :min="1"
              :max-fraction-digits="0"
              size="small"
              fluid
              @update:model-value="(value) => setLotQuantity(row, value)"
            />

            <label :id="`${uid}-priority-label-${row.made_item_id}-${row.project.id}`" :for="`${uid}-priority-${row.made_item_id}-${row.project.id}`" class="field-label">
              {{ t('madeItems.demands.manageLots.priority') }}
            </label>
            <Select
              v-model="row.priority"
              :input-id="`${uid}-priority-${row.made_item_id}-${row.project.id}`"
              :aria-labelledby="`${uid}-priority-label-${row.made_item_id}-${row.project.id}`"
              :options="priorityOptions"
              option-label="label"
              option-value="value"
              size="small"
              fluid
            />

            <label :for="`${uid}-required-delivery-date-${row.made_item_id}-${row.project.id}`" class="field-label">{{
              t('madeItems.demands.manageLots.requiredDeliveryDate')
            }}</label>
            <DatePicker
              v-model="row.requiredDeliveryDate"
              :input-id="`${uid}-required-delivery-date-${row.made_item_id}-${row.project.id}`"
              show-button-bar
              show-clear
              size="small"
              fluid
            />
          </div>

          <div class="demands-section">
            <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- captions every row below, each control names it through aria-labelledby -->
            <label
              v-if="row.demands.length > 1"
              :id="`${uid}-contributing-demands-${row.made_item_id}-${row.project.id}`"
              class="field-label"
            >
              {{ t('madeItems.demands.manageLots.contributingDemands') }}
            </label>
            <div v-for="demand in row.demands" :key="demand.id" class="demand-row">
              <span :id="`${uid}-demand-${demand.id}`" class="demand-id">#{{ demand.id }}</span>
              <InputNumber
                :aria-labelledby="`${uid}-contributing-demands-${row.made_item_id}-${row.project.id} ${uid}-demand-${demand.id}`"
                :model-value="demand.quantity"
                :min="0"
                :max="demand.maxQuantity"
                :max-fraction-digits="0"
                :input-style="{ width: '5.5rem' }"
                size="small"
                @update:model-value="(value) => setDemandQuantity(row, demand, value)"
              />
              <Button
                icon="mdi mdi-close"
                severity="secondary"
                text
                rounded
                size="small"
                v-tooltip.focus="t('madeItems.demands.manageLots.removeDemand')"
                :aria-label="t('madeItems.demands.manageLots.removeDemand')"
                @click="removeDemand(demand.id)"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="panel-footer">
      <Message v-if="errorMessage" severity="error" :closable="false" size="small">
        {{ errorMessage }}
      </Message>
      <Button
        :label="t('madeItems.demands.manageLots.createLots')"
        icon="mdi mdi-factory"
        :disabled="editableRows.length === 0"
        :loading="submitting"
        fluid
        @click="onSubmit"
      />
      <Button
        v-if="procurementStore.selectedDemands.length > 0"
        :label="t('madeItems.demands.manageLots.clearSelection')"
        severity="secondary"
        outlined
        size="small"
        fluid
        @click="procurementStore.clearSelection()"
      />
    </div>
  </Panel>
</template>

<style scoped lang="scss">
.manage-lots-panel {
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

.global-overwrite {
  flex-shrink: 0;
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  column-gap: var(--space-2);
  row-gap: var(--space-2);
  padding-bottom: var(--space-3);
  margin-bottom: var(--space-1);
  border-bottom: 1px solid var(--p-content-border-color);
}

.rows-section {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.panel-footer {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}



.rows-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.row-card {
  position: relative;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  padding: var(--space-2) var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.row-card--zero-qty {
  border-color: var(--p-orange-500);
}

.zero-qty-badge {
  position: absolute;
  top: 0.5rem;
  right: 0.625rem;
  color: var(--p-orange-500);
  font-size: var(--font-size-md);
  cursor: help;
}

.row-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-bottom: var(--space-2);
}

.row-name {
  font-weight: 600;
  font-size: var(--font-size-sm);
}

.row-code,
.row-project {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.row-controls {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  column-gap: var(--space-2);
  row-gap: var(--space-2);
}

.field-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
}

.demands-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.demand-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.demand-id {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  min-width: 2.5rem;
}
</style>
