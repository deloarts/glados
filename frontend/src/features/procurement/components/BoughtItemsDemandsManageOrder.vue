<script setup lang="ts">
import { extractApiError } from '@/core/utils/errors'
import { roundTo } from '@/core/utils/numbers'
import { dateToParam, earlierDate, toLocalDayStart } from '@/core/utils/dates'
import { currencyInputPrefix } from '@/core/utils/currency'
import { computed, onMounted, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useBoughtItemsProcurementStore } from '../stores/boughtItemsProcurementStore'
import { useBoughtItemsAllocationsStore } from '../stores/boughtItemsAllocationsStore'
import { useSuppliersStore } from '@/features/suppliers'
import { getOrders } from '@/features/orders'
import { createOrderItem } from '@/features/orders'

import { OrderCreateForm } from '@/features/orders'

import type { OrderResponse } from '@/features/orders'
import type { ProjectRef } from '@/core/types/projectRef'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { formatUnit } from '@/shared/utils/units'
import { useBoughtItemsDemandsStore, BoughtItemSelect } from '@/features/bought-items'
import type { BoughtItemResponse } from '@/features/bought-items'
import EmptyState from '@/shared/components/EmptyState.vue'

defineOptions({ inheritAttrs: false })

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const { toastOnError } = useErrorToast()

const procurementStore = useBoughtItemsProcurementStore()
const allocationsStore = useBoughtItemsAllocationsStore()
const demandsStore = useBoughtItemsDemandsStore()
const suppliersStore = useSuppliersStore()

// ── Draft orders ─────────────────────────────────────────────────────
// A partially ordered order still takes new lines as a draft does, so the
// picker offers both.

const draftOrders = ref<OrderResponse[]>([])
const loadingOrders = ref(false)
const selectedOrder = ref<OrderResponse | null>(null)
const showCreateOrder = ref(false)

async function loadDraftOrders(): Promise<void> {
  loadingOrders.value = true
  try {
    const result = await getOrders({ status: ['draft', 'partially_ordered'], limit: API_MAX_PAGE_SIZE })
    draftOrders.value = result.items
  } finally {
    loadingOrders.value = false
  }
}

function onOrderCreated(order: OrderResponse): void {
  draftOrders.value = [order, ...draftOrders.value]
  selectedOrder.value = order
  rebuildRows()
}

// ── Aggregated rows ──────────────────────────────────────────────────

// One demand's share of a row's line, by default what it still needs.
interface RowDemand {
  id: number
  quantity: number
}

// eslint-disable-next-line no-restricted-syntax -- editable table row state aggregated from several demands
interface EditableRow {
  key: string
  item_id: number
  item_order_code_1: string
  item_article_name: string
  project: ProjectRef
  unit: string
  quantity: number
  // True once the buyer typed the line quantity, for example a pack size;
  // until then it follows the sum of the shares.
  quantityEdited: boolean
  price: number | null
  supplier_id: number | null
  demands: RowDemand[]
  hasMismatch: boolean
  substituteItem: BoughtItemResponse | null
  substituteReason: string
  expectedDeliveryDate: Date | null
}

const editableRows = ref<EditableRow[]>([])
// Demands the buyer ordered separately, each on its own row, so it can take
// its own substitute or quantity.
const separatedDemandIds = ref(new Set<number>())

function sharesTotal(row: EditableRow): number {
  return roundTo(
    row.demands.reduce((sum, d) => sum + (d.quantity || 0), 0),
    6,
  )
}

function sharesExceedLine(row: EditableRow): boolean {
  return sharesTotal(row) > row.quantity + 1e-6
}

function onShareChanged(row: EditableRow): void {
  if (!row.quantityEdited) row.quantity = sharesTotal(row)
}

function onLineQuantityChanged(row: EditableRow): void {
  row.quantityEdited = true
}

function separateDemand(demandId: number): void {
  separatedDemandIds.value = new Set([...separatedDemandIds.value, demandId])
  rebuildRows()
}

function joinDemand(demandId: number): void {
  const next = new Set(separatedDemandIds.value)
  next.delete(demandId)
  separatedDemandIds.value = next
  rebuildRows()
}

// Rebuilt from the selection whenever it changes; what the buyer entered on
// a row, its shares included, is kept for every row and demand still there.
function rebuildRows(): void {
  const previous = new Map(editableRows.value.map((row) => [row.key, row]))
  const previousShares = new Map(
    editableRows.value.flatMap((row) => row.demands.map((d) => [d.id, d.quantity] as const)),
  )
  const map = new Map<string, EditableRow>()

  for (const d of procurementStore.selectedDemands) {
    const share =
      previousShares.get(d.id) ?? allocationsStore.getSummary(d.id)?.unallocated ?? d.quantity
    const key = separatedDemandIds.value.has(d.id)
      ? `demand:${d.id}`
      : `${d.item_id}|${d.unit}|${d.project_id}`
    // The row snapshot can go stale, so the live demand's date wins.
    const liveDemand = demandsStore.items.find((item) => item.id === d.id)
    const desiredDate = liveDemand?.desired_delivery_date ?? d.desired_delivery_date
    const demandDate = desiredDate ? toLocalDayStart(desiredDate) : null
    const existing = map.get(key)
    if (existing) {
      existing.demands.push({ id: d.id, quantity: share })
      existing.expectedDeliveryDate = earlierDate(existing.expectedDeliveryDate, demandDate)
    } else {
      const kept = previous.get(key)
      map.set(key, {
        key,
        item_id: d.item_id,
        item_order_code_1: d.item_order_code_1,
        item_article_name: d.item_article_name,
        project: {
          id: d.project_id,
          project_number: d.project_number,
          customer: { name: d.project_customer },
          description: d.project_description,
        },
        unit: d.unit,
        quantity: kept?.quantityEdited ? kept.quantity : 0,
        quantityEdited: kept?.quantityEdited ?? false,
        price: kept?.price ?? null,
        supplier_id: kept?.supplier_id ?? selectedOrder.value?.supplier_id ?? null,
        demands: [{ id: d.id, quantity: share }],
        hasMismatch: false,
        substituteItem: kept?.substituteItem ?? null,
        substituteReason: kept?.substituteReason ?? '',
        expectedDeliveryDate: kept?.expectedDeliveryDate ?? demandDate,
      })
    }
  }

  for (const row of map.values()) {
    if (!row.quantityEdited) row.quantity = sharesTotal(row)
  }

  // Mark unit mismatches (same item_id, different units)
  const unitsByItem = new Map<number, Set<string>>()
  for (const row of map.values()) {
    if (!unitsByItem.has(row.item_id)) unitsByItem.set(row.item_id, new Set())
    unitsByItem.get(row.item_id)!.add(row.unit)
  }
  for (const row of map.values()) {
    row.hasMismatch = (unitsByItem.get(row.item_id)?.size ?? 0) > 1
  }

  editableRows.value = [...map.values()]
}

const canSubmit = computed(
  () =>
    editableRows.value.length > 0 &&
    !!selectedOrder.value &&
    editableRows.value.every((row) => row.quantity > 0 && !sharesExceedLine(row)),
)

// selectedDemands is replaced wholesale, so a shallow watch suffices.
watch(
  () => procurementStore.selectedDemands,
  () => rebuildRows(),
)

watch(selectedOrder, (order) => {
  for (const row of editableRows.value) {
    row.supplier_id = order?.supplier_id ?? null
  }
})

// ── Submit ───────────────────────────────────────────────────────────

const submitting = ref(false)
const errorMessage = ref<string | null>(null)

async function onSubmit(): Promise<void> {
  if (!selectedOrder.value) {
    errorMessage.value = t('boughtItems.demands.procure.errors.noOrder')
    return
  }
  if (editableRows.value.length === 0) return

  submitting.value = true
  errorMessage.value = null

  try {
    for (const row of editableRows.value) {
      const orderedItemId = row.substituteItem?.id ?? row.item_id
      await createOrderItem(selectedOrder.value.id, {
        bought_item_id: orderedItemId,
        supplier_id: row.supplier_id ?? selectedOrder.value.supplier_id,
        project_id: row.project.id,
        quantity: row.quantity,
        unit: row.unit,
        items_per_unit: 1,
        price: row.price !== null ? Math.round(row.price * 100) : null,
        bought_demand_allocations: row.demands
          .filter((d) => d.quantity > 0)
          .map((d) => ({ demand_item_id: d.id, quantity: d.quantity })),
        substitute_reason: row.substituteItem ? row.substituteReason.trim() || null : null,
        expected_delivery_date: dateToParam(row.expectedDeliveryDate),
      })
    }
    procurementStore.clearSelection()
    procurementStore.triggerRefresh()
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('boughtItems.demands.procure.errors.unknown')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadDraftOrders().catch(toastOnError())
  if (suppliersStore.items.length === 0) {
    void suppliersStore.refresh()
  }
})
</script>

<template>
  <Panel class="manage-order-panel fill-panel" v-bind="$attrs">
    <template #header>
      <div class="panel-header-row">
        <span class="panel-title">{{ t('boughtItems.demands.procure.title') }}</span>
        <Tag
          v-if="procurementStore.selectedDemands.length > 0"
          :value="
            t('boughtItems.demands.procure.selectedCount', {
              count: procurementStore.selectedDemands.length,
            })
          "
          severity="secondary"
        />
      </div>
    </template>

    <!-- Order selector -->
    <div class="order-section">
      <label :id="`${uid}-order-label`" :for="`${uid}-order`" class="field-label">
        {{ t('boughtItems.demands.procure.order') }}
      </label>
      <div class="order-select-row">
        <Select
          v-model="selectedOrder"
          :input-id="`${uid}-order`"
          :aria-labelledby="`${uid}-order-label`"
          :options="draftOrders"
          :option-label="(o: OrderResponse) => `${o.order_number} (${o.supplier_name})`"
          :loading="loadingOrders"
          :placeholder="t('boughtItems.demands.procure.selectOrder')"
          show-clear
          fluid
          size="small"
        />
        <Button
          icon="mdi mdi-refresh"
          severity="secondary"
          text
          rounded
          size="small"
          :loading="loadingOrders"
          v-tooltip.focus="t('boughtItems.demands.procure.refreshOrders')"
          :aria-label="t('boughtItems.demands.procure.refreshOrders')"
          @click="loadDraftOrders"
        />
        <Button
          icon="mdi mdi-plus"
          severity="secondary"
          text
          rounded
          size="small"
          v-tooltip.focus="t('boughtItems.demands.procure.createOrder')"
          :aria-label="t('boughtItems.demands.procure.createOrder')"
          @click="showCreateOrder = true"
        />
      </div>
    </div>

    <!-- Aggregated rows -->
    <div class="rows-section">
      <EmptyState v-if="editableRows.length === 0" :message="t('boughtItems.demands.procure.noSelection')" icon="mdi mdi-checkbox-marked-outline" />

      <div v-else class="rows-list">
        <div
          v-for="row in editableRows"
          :key="row.key"
          class="row-card"
          :class="{ 'row-card--mismatch': row.hasMismatch }"
        >
          <div class="row-item">
            <span class="row-name">{{ row.item_article_name }}</span>
            <span class="row-code">{{ row.item_order_code_1 }}</span>
            <span class="row-project">{{ row.project.project_number }}</span>
            <span
              v-if="row.hasMismatch"
              class="mismatch-badge"
              v-tooltip="t('boughtItems.demands.procure.unitMismatch')"
            >
              <i class="mdi mdi-alert" aria-hidden="true" />
            </span>
          </div>

          <div class="row-controls">
            <div class="row-qty">
              <InputNumber
                v-model="row.quantity"
                :min="0.001"
                :max-fraction-digits="3"
                :input-style="{ width: '6rem' }"
                size="small"
                @update:model-value="onLineQuantityChanged(row)"
              />
              <span class="row-unit">{{ formatUnit(row.unit) }}</span>
            </div>

            <div class="row-price">
              <InputNumber
                v-model="row.price"
                :min="0"
                :min-fraction-digits="2"
                :max-fraction-digits="2"
                :prefix="currencyInputPrefix()"
                :input-style="{ width: '6rem' }"
                size="small"
              />
              <span class="row-price-label">{{
                t('boughtItems.demands.procure.pricePerUnit')
              }}</span>
            </div>

            <Select
              v-model="row.supplier_id"
              :aria-label="t('boughtItems.demands.procure.supplier')"
              :options="suppliersStore.items"
              option-label="name"
              option-value="id"
              :loading="suppliersStore.loading"
              :placeholder="t('boughtItems.demands.procure.supplier')"
              show-clear
              fluid
              size="small"
            />

            <div class="row-delivery-date">
              <DatePicker
                v-model="row.expectedDeliveryDate"
                show-button-bar
                show-clear
                size="small"
                fluid
              />
              <span class="row-delivery-date-label">{{
                t('boughtItems.demands.procure.expectedDeliveryDate')
              }}</span>
            </div>
          </div>

          <!-- The share of the line each demand takes -->
          <div class="row-demands">
            <div v-for="share in row.demands" :key="share.id" class="row-demand">
              <span class="row-demand-label">{{
                t('boughtItems.demands.procure.demandShare', { id: share.id })
              }}</span>
              <InputNumber
                v-model="share.quantity"
                :min="0"
                :max-fraction-digits="3"
                :input-style="{ width: '6rem' }"
                size="small"
                @update:model-value="onShareChanged(row)"
              />
              <span class="row-unit">{{ formatUnit(row.unit) }}</span>
              <Button
                v-if="row.demands.length > 1"
                :label="t('boughtItems.demands.procure.separateDemand')"
                severity="secondary"
                text
                size="small"
                @click="separateDemand(share.id)"
              />
              <Button
                v-else-if="separatedDemandIds.has(share.id)"
                :label="t('boughtItems.demands.procure.joinDemand')"
                severity="secondary"
                text
                size="small"
                @click="joinDemand(share.id)"
              />
            </div>
            <Message v-if="sharesExceedLine(row)" severity="warn" size="small" :closable="false">
              {{ t('boughtItems.demands.procure.sharesExceedLine') }}
            </Message>
          </div>

          <!-- Substitute item -->
          <div class="substitute-section">
            <label :id="`${uid}-substitute-item-label-${row.key}`" :for="`${uid}-substitute-item-${row.key}`" class="field-label">
              {{ t('boughtItems.demands.procure.substituteItem') }}
            </label>
            <BoughtItemSelect
              v-model="row.substituteItem"
              :input-id="`${uid}-substitute-item-${row.key}`"
              :aria-labelledby="`${uid}-substitute-item-label-${row.key}`"
              :exclude-id="row.item_id"
              :placeholder="t('boughtItems.demands.procure.substituteItemPlaceholder')"
              show-clear
              fluid
              size="small"
            />
            <InputText
              v-if="row.substituteItem"
              v-model="row.substituteReason"
              :placeholder="t('boughtItems.demands.procure.substituteReason')"
              size="small"
              fluid
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="panel-footer">
      <Message v-if="errorMessage" severity="error" :closable="false" size="small">
        {{ errorMessage }}
      </Message>
      <Button
        :label="t('boughtItems.demands.procure.addToOrder')"
        icon="mdi mdi-cart-arrow-right"
        :disabled="!canSubmit"
        :loading="submitting"
        fluid
        @click="onSubmit"
      />
      <Button
        v-if="procurementStore.selectedDemands.length > 0"
        :label="t('boughtItems.demands.procure.clearSelection')"
        severity="secondary"
        outlined
        size="small"
        fluid
        @click="procurementStore.clearSelection()"
      />
    </div>
  </Panel>

  <OrderCreateForm v-model:visible="showCreateOrder" @created="onOrderCreated" />
</template>

<style scoped lang="scss">
.manage-order-panel {
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

.order-section {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.field-label {
  padding-top: var(--space-3);
  font-size: var(--font-size-sm);
  font-weight: 500;
}

.order-select-row {
  display: flex;
  align-items: center;
  gap: var(--space-1);
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

.row-card--mismatch {
  border-color: var(--p-orange-400);
}

.row-item {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  flex-wrap: wrap;
  flex-direction: column;
  padding-bottom: var(--space-3);
}

.row-name {
  font-weight: 600;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);

  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-code,
.row-project {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);

  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mismatch-badge {
  color: var(--p-orange-500);
  font-size: var(--font-size-sm);
  cursor: help;
}

.row-demands {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.row-demand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.row-demand-label {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  min-width: 6rem;
}

.substitute-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.row-controls {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.row-qty {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.row-unit {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.row-price {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.row-price-label {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.row-delivery-date {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.row-delivery-date-label {
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
