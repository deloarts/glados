<script setup lang="ts">
import { computed, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { extractApiError } from '@/core/utils/errors'
import { dateToParam as formatDate } from '@/core/utils/dates'
import { currencyInputPrefix } from '@/core/utils/currency'
import { HelpButton } from '@/shared/help'
import { OrderSelect } from '@/features/orders'
import { OrderCreateForm } from '@/features/orders'
import { assignExternalPosition } from '../api/assignExternalPosition'
import { MADE_ITEM_ORDER_UNIT } from '../../utils/madeItemOrderUnit'
import { useProductionLotsStore } from '../../stores/productionLotsStore'
import { useProductionLotsSelectionStore } from '../stores/productionLotsSelectionStore'
import { useMachineCapability } from '../../composables/useMachineCapability'
import { sortedSteps, stepMethodLabel } from '../../utils/lotStepDisplay'

import type { OrderResponse } from '@/features/orders'
import type { SelectedItem } from '../stores/productionLotsSelectionStore'
import EmptyState from '@/shared/components/EmptyState.vue'

defineOptions({ inheritAttrs: false })

const emit = defineEmits<{
  assigned: []
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const lotsStore = useProductionLotsStore()
const selectionStore = useProductionLotsSelectionStore()
const { positionHasExternalMethods, getPreferredSupplierId } = useMachineCapability()

const showCreateOrder = ref(false)

// Pre-fills the create-order form's supplier from the first selected
// position. It is a hint only, overridable in the form.
const presetSupplierId = computed<number | null>(() => {
  const first = selectionStore.items[0]
  return first ? getPreferredSupplierId(first.position) : null
})

function onOrderCreated(order: OrderResponse): void {
  selectionStore.selectedOrder = order
}

// ── Per-row editable fields ──────────────────────────────────────────

interface RowForm {
  quantity: number
  price: number | null
  expected_delivery_date: Date | null
  expected_pickup_date: Date | null
}

function rowKey(item: SelectedItem): string {
  return `${item.lotId}:${item.position.id}`
}

const rowForms = reactive<Record<string, RowForm>>({})

watch(
  () => selectionStore.items,
  (items) => {
    const keys = new Set(items.map(rowKey))
    for (const key of Object.keys(rowForms)) {
      if (!keys.has(key)) delete rowForms[key]
    }
    for (const item of items) {
      const key = rowKey(item)
      if (!rowForms[key]) {
        rowForms[key] = {
          quantity: item.position.quantity_remaining,
          price: null,
          expected_delivery_date: null,
          expected_pickup_date: null,
        }
      }
    }
  },
  { immediate: true },
)

// ── Submit ───────────────────────────────────────────────────────────

const submitting = ref(false)
const errorMessage = ref<string | null>(null)

async function onSubmit(): Promise<void> {
  const order = selectionStore.selectedOrder
  if (!order || selectionStore.items.length === 0) return

  submitting.value = true
  errorMessage.value = null
  const failedLabels: string[] = []
  let anySucceeded = false

  for (const item of selectionStore.items) {
    const form = rowForms[rowKey(item)]
    try {
      await assignExternalPosition(item.lotId, item.position.id, {
        order_id: order.id,
        unit: MADE_ITEM_ORDER_UNIT,
        items_per_unit: 1,
        price: form?.price != null ? Math.round(form.price * 100) : null,
        expected_delivery_date: formatDate(form?.expected_delivery_date ?? null),
        expected_pickup_date: formatDate(form?.expected_pickup_date ?? null),
        quantity: form?.quantity ?? item.position.quantity_remaining,
      })
      selectionStore.removeItem(item.lotId, item.position.id)
      anySucceeded = true
    } catch (e) {
      failedLabels.push(`${item.lotNumber} #${item.position.sequence}`)
      errorMessage.value =
        extractApiError(e) ?? t('production.lots.detail.manageOrders.errors.unknown')
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

function onClear(): void {
  selectionStore.clearSelection()
}
</script>

<template>
  <Panel class="manage-orders-panel fill-panel" v-bind="$attrs">
    <template #header>
      <div class="panel-header-row">
        <div class="panel-header-main">
          <span class="panel-title">{{ t('production.lots.detail.manageOrders.title') }}</span>
          <Tag
            v-if="selectionStore.items.length > 0"
            :value="
              t('production.lots.listManage.selectedCount', { count: selectionStore.items.length })
            "
            severity="secondary"
          />
        </div>
        <HelpButton slug="production/manage-orders" size="small" rounded />
      </div>
    </template>

    <div class="order-section">
      <label :id="`${uid}-select-order-label`" :for="`${uid}-select-order`" class="field-label">
        {{ t('production.lots.detail.manageOrders.selectOrder') }}
      </label>
      <div class="order-select-row">
        <OrderSelect
          v-model="selectionStore.selectedOrder"
          :input-id="`${uid}-select-order`"
          :aria-labelledby="`${uid}-select-order-label`"
          fluid
          size="small"
        />
        <Button
          icon="mdi mdi-plus"
          severity="secondary"
          text
          rounded
          size="small"
          v-tooltip.focus="t('production.lots.detail.manageOrders.createOrder')"
          :aria-label="t('production.lots.detail.manageOrders.createOrder')"
          @click="showCreateOrder = true"
        />
      </div>
    </div>

    <EmptyState v-if="selectionStore.items.length === 0" :message="t('production.lots.listManage.selectStepPrompt')" icon="mdi mdi-cursor-default-click-outline" />

    <div v-else class="rows-section">
      <div class="rows-list">
        <div v-for="item in selectionStore.items" :key="rowKey(item)" class="row-card">
          <div class="row-header row-header--static">
            <span class="row-seq">{{ item.lotNumber }} #{{ item.position.sequence }}</span>
            <div class="row-chips">
              <span v-for="step in sortedSteps(item.position)" :key="step.id" class="step-chip">
                <span class="step-chip-method">{{ stepMethodLabel(step) }}</span>
              </span>
            </div>
            <span class="row-qty"
              >{{ item.position.quantity_remaining }} / {{ item.position.quantity }}</span
            >
            <i
              v-if="!positionHasExternalMethods(item.position)"
              class="mdi mdi-alert external-note-icon"
              v-tooltip.top="t('production.lots.detail.manageOrders.noExternalMethodTooltip')"
            />
            <Button
              icon="mdi mdi-close"
              severity="secondary"
              text
              rounded
              size="small"
              :aria-label="t('production.lots.listManage.removeFromSelection')"
              @click="selectionStore.removeItem(item.lotId, item.position.id)"
            />
          </div>

          <div v-if="rowForms[rowKey(item)]" class="row-fields">
            <InputNumber
              v-model="rowForms[rowKey(item)]!.quantity"
              :min="1"
              :max="item.position.quantity_remaining"
              :max-fraction-digits="0"
              :placeholder="t('production.lots.detail.assign.fields.quantity')"
              size="small"
            />
            <InputNumber
              v-model="rowForms[rowKey(item)]!.price"
              :min="0"
              :min-fraction-digits="2"
              :max-fraction-digits="2"
              :prefix="currencyInputPrefix()"
              :placeholder="t('production.lots.detail.assign.fields.price')"
              size="small"
            />
            <DatePicker
              v-model="rowForms[rowKey(item)]!.expected_delivery_date"
              show-button-bar
              show-clear
              :placeholder="t('production.lots.detail.assign.fields.expectedDelivery')"
              size="small"
            />
            <DatePicker
              v-model="rowForms[rowKey(item)]!.expected_pickup_date"
              show-button-bar
              show-clear
              :placeholder="t('production.lots.detail.assign.fields.expectedPickup')"
              size="small"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="panel-footer">
      <Message v-if="errorMessage" severity="error" :closable="false" size="small">
        {{ errorMessage }}
      </Message>
      <Button
        :label="t('production.lots.detail.manageOrders.confirm')"
        icon="mdi mdi-truck-outline"
        :disabled="!selectionStore.selectedOrder || selectionStore.items.length === 0"
        :loading="submitting"
        fluid
        @click="onSubmit"
      />
      <Button
        v-if="selectionStore.items.length > 0 || selectionStore.selectedOrder"
        :label="t('production.lots.listManage.clearSelection')"
        severity="secondary"
        outlined
        size="small"
        fluid
        @click="onClear"
      />
    </div>
  </Panel>

  <OrderCreateForm
    v-model:visible="showCreateOrder"
    :preset-supplier-id="presetSupplierId"
    @created="onOrderCreated"
  />
</template>

<style scoped lang="scss">
.manage-orders-panel {
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

// Title and count stay together on the left so the explain button can hold the
// far right of the header on its own.
.panel-header-main {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.order-section {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.field-label {
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

.row-chips {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.step-chip {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  background: var(--p-surface-50);
}

.p-dark .step-chip {
  background: var(--p-surface-800);
}

.step-chip-method {
  font-size: var(--font-size-xs);
  font-weight: 600;
}

.row-qty {
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
  color: var(--p-text-muted-color);
  white-space: nowrap;
}

.external-note-icon {
  color: var(--p-orange-500);
  font-size: var(--font-size-sm);
  cursor: help;
}

.row-fields {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-2);
  padding: 0 var(--space-2) var(--space-2);
  border-top: 1px solid var(--p-content-border-color);
  padding-top: var(--space-2);
}

.panel-footer {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
</style>
