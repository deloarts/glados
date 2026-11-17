<script setup lang="ts">
import { computed, reactive, ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { hasAction } from '@/core/utils/lifecycleActions'
import { extractApiError } from '@/core/utils/errors'
import { dateToParam as formatDate } from '@/core/utils/dates'
import { currencyInputPrefix } from '@/core/utils/currency'
import { OrderSelect } from '@/features/orders'
import { OrderCreateForm } from '@/features/orders'
import { HelpButton } from '@/shared/help'
import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'
import { useMachineCapability } from '../../composables/useMachineCapability'
import { sortedSteps, stepMethodLabel } from '../../utils/lotStepDisplay'

import type { OrderResponse } from '@/features/orders'
import type { LotPositionResponse } from '../../types/productionLotsResponse'
import { BOUGHT_ITEM_UNIT_CODES } from '@/shared/utils/units'
import { bySequence } from '../../utils/sequence'
import EmptyState from '@/shared/components/EmptyState.vue'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  lotId: number
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const detailStore = useProductionLotDetailStore()
const { positionHasExternalMethods, getPreferredSupplierId } = useMachineCapability()

// ── Order selection ──────────────────────────────────────────────────

const selectedOrder = ref<OrderResponse | null>(null)
const showCreateOrder = ref(false)

// Supplier hint from the expanded position; the form can override it.
const presetSupplierId = computed<number | null>(() => {
  const position = unassignedPositions.value.find((p) => p.id === expandedPositionId.value)
  return position ? getPreferredSupplierId(position) : null
})

function onOrderCreated(order: OrderResponse): void {
  selectedOrder.value = order
}

// ── Unassigned positions ─────────────────────────────────────────────

// Positions that offer an external assignment: no order item yet. An
// internal position can still take an external share and becomes mixed.
const unassignedPositions = computed<LotPositionResponse[]>(() =>
  [...(detailStore.lot?.positions ?? [])]
    .filter((p) => hasAction(p, 'assign_external'))
    .sort(bySequence),
)

// ── Inline per-position assign form ──────────────────────────────────

interface AssignForm {
  quantity: number
  unit: string
  items_per_unit: number
  price: number | null
  expected_delivery_date: Date | null
  expected_pickup_date: Date | null
}

function createEmptyForm(quantity: number): AssignForm {
  return {
    quantity,
    unit: '',
    items_per_unit: 1,
    price: null,
    expected_delivery_date: null,
    expected_pickup_date: null,
  }
}

const unitOptions = BOUGHT_ITEM_UNIT_CODES.map((code) => ({ value: code, code }))

const expandedPositionId = ref<number | null>(null)
const form = reactive(createEmptyForm(0))
const submitting = ref(false)
const errorMessage = ref<string | null>(null)

function toggleExpand(position: LotPositionResponse): void {
  if (!selectedOrder.value) return
  if (expandedPositionId.value === position.id) {
    expandedPositionId.value = null
    return
  }
  expandedPositionId.value = position.id
  Object.assign(form, createEmptyForm(position.quantity_remaining))
  errorMessage.value = null
}

function isFormValid(): boolean {
  return form.unit.trim().length > 0 && form.quantity > 0
}

async function onConfirm(position: LotPositionResponse): Promise<void> {
  if (!selectedOrder.value || !detailStore.lot || !isFormValid()) {
    errorMessage.value = t('production.lots.detail.manageOrders.errors.required')
    return
  }

  submitting.value = true
  errorMessage.value = null

  try {
    await detailStore.assignPosition(props.lotId, position.id, {
      order_id: selectedOrder.value.id,
      unit: form.unit.trim(),
      items_per_unit: form.items_per_unit,
      price: form.price !== null ? Math.round(form.price * 100) : null,
      expected_delivery_date: formatDate(form.expected_delivery_date),
      expected_pickup_date: formatDate(form.expected_pickup_date),
      quantity: form.quantity,
    })
    expandedPositionId.value = null
  } catch (e) {
    errorMessage.value =
      extractApiError(e) ?? t('production.lots.detail.manageOrders.errors.unknown')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Panel class="manage-orders-panel fill-panel" v-bind="$attrs">
    <template #header>
      <div class="panel-header-row">
        <div class="panel-header-main">
          <span class="panel-title">{{ t('production.lots.detail.manageOrders.title') }}</span>
          <Tag
            v-if="unassignedPositions.length > 0"
            :value="
              t('production.lots.detail.manageOrders.unassignedCount', {
                count: unassignedPositions.length,
              })
            "
            severity="secondary"
          />
        </div>
        <HelpButton slug="production/manage-orders" size="small" rounded />
      </div>
    </template>

    <!-- Order selector -->
    <div class="order-section">
      <label :id="`${uid}-select-order-label`" :for="`${uid}-select-order`" class="field-label">
        {{ t('production.lots.detail.manageOrders.selectOrder') }}
      </label>
      <div class="order-select-row">
        <OrderSelect
          v-model="selectedOrder"
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

    <!-- Unassigned positions -->
    <div class="rows-section">
      <EmptyState v-if="unassignedPositions.length === 0" :message="t('production.lots.detail.manageOrders.noPositions')" icon="mdi mdi-truck-outline" />

      <div v-else class="rows-list">
        <div v-for="position in unassignedPositions" :key="position.id" class="row-card">
          <div
            class="row-header"
            :class="{ 'row-header--disabled': !selectedOrder }"
            role="button"
            tabindex="0"
            v-tooltip="
              !selectedOrder ? t('production.lots.detail.manageOrders.selectOrderFirst') : undefined
            "
            @click="toggleExpand(position)"
            @keydown.enter="toggleExpand(position)"
            @keydown.space.prevent="toggleExpand(position)"
          >
            <span class="row-seq">#{{ position.sequence }}</span>
            <div class="row-chips">
              <span v-for="step in sortedSteps(position)" :key="step.id" class="step-chip">
                <span class="step-chip-method">{{ stepMethodLabel(step) }}</span>
                <span class="step-chip-seq">#{{ step.sequence }}</span>
              </span>
            </div>
            <span class="row-qty">{{ position.quantity_remaining }} / {{ position.quantity }}</span>
            <i
              v-if="!positionHasExternalMethods(position)"
              class="mdi mdi-alert external-note-icon"
              aria-hidden="true"
              v-tooltip.top="t('production.lots.detail.manageOrders.noExternalMethodTooltip')"
            />
            <i
              class="mdi row-chevron"
              :class="expandedPositionId === position.id ? 'mdi-chevron-up' : 'mdi-chevron-down'"
              aria-hidden="true"
            />
          </div>

          <form
            v-if="expandedPositionId === position.id"
            class="row-form"
            @submit.prevent="onConfirm(position)"
          >
            <div class="form-grid">
              <div class="field">
                <label :for="`${uid}-quantity-${position.id}`">
                  {{ t('production.lots.detail.assign.fields.quantity') }} *
                </label>
                <InputNumber
                  v-model="form.quantity"
                  :input-id="`${uid}-quantity-${position.id}`"
                  :min="1"
                  :max="position.quantity_remaining"
                  :max-fraction-digits="0"
                  size="small"
                  fluid
                />
              </div>
              <div class="field">
                <label :id="`${uid}-unit-label-${position.id}`" :for="`${uid}-unit-${position.id}`">
                  {{ t('production.lots.detail.assign.fields.unit') }} *
                </label>
                <Select
                  v-model="form.unit"
                  :input-id="`${uid}-unit-${position.id}`"
                  :aria-labelledby="`${uid}-unit-label-${position.id}`"
                  :options="unitOptions"
                  option-label="code"
                  option-value="value"
                  size="small"
                  fluid
                />
              </div>
              <div class="field">
                <label :for="`${uid}-items-per-unit-${position.id}`">
                  {{ t('production.lots.detail.assign.fields.itemsPerUnit') }}
                </label>
                <InputNumber
                  v-model="form.items_per_unit"
                  :input-id="`${uid}-items-per-unit-${position.id}`"
                  :min="0.001"
                  :max-fraction-digits="3"
                  size="small"
                  fluid
                />
              </div>
              <div class="field">
                <label :for="`${uid}-price-${position.id}`">
                  {{ t('production.lots.detail.assign.fields.price') }}
                </label>
                <InputNumber
                  v-model="form.price"
                  :input-id="`${uid}-price-${position.id}`"
                  :min="0"
                  :min-fraction-digits="2"
                  :max-fraction-digits="2"
                  :prefix="currencyInputPrefix()"
                  size="small"
                  fluid
                />
              </div>
              <div class="field">
                <label :for="`${uid}-expected-delivery-${position.id}`">
                  {{ t('production.lots.detail.assign.fields.expectedDelivery') }}
                </label>
                <DatePicker
                  v-model="form.expected_delivery_date"
                  :input-id="`${uid}-expected-delivery-${position.id}`"
                  show-button-bar
                  show-clear
                  size="small"
                  fluid
                />
              </div>
              <div class="field">
                <label :for="`${uid}-expected-pickup-${position.id}`">
                  {{ t('production.lots.detail.assign.fields.expectedPickup') }}
                </label>
                <DatePicker
                  v-model="form.expected_pickup_date"
                  :input-id="`${uid}-expected-pickup-${position.id}`"
                  show-button-bar
                  show-clear
                  size="small"
                  fluid
                />
              </div>
            </div>

            <Message v-if="errorMessage" severity="error" :closable="false" size="small">
              {{ errorMessage }}
            </Message>

            <div class="row-form-actions">
              <Button
                :label="t('common.cancel')"
                severity="secondary"
                outlined
                size="small"
                :disabled="submitting"
                @click.stop="expandedPositionId = null"
              />
              <Button
                :label="t('production.lots.detail.manageOrders.confirm')"
                icon="mdi mdi-truck-outline"
                size="small"
                type="submit"
                :loading="submitting"
                :disabled="!isFormValid()"
              />
            </div>
          </form>
        </div>
      </div>
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
// right edge.
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
  cursor: pointer;

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: -2px;
  }
}

.row-header--disabled {
  cursor: default;
  opacity: 0.6;
}

.row-seq {
  font-weight: 700;
  font-size: var(--font-size-sm);
}

.row-chips {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.step-chip {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
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

.step-chip-seq {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.row-qty {
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
  color: var(--p-text-muted-color);
  white-space: nowrap;
}

.row-chevron {
  color: var(--p-text-muted-color);
}

.external-note-icon {
  color: var(--p-orange-500);
  font-size: var(--font-size-sm);
  cursor: help;
}

.row-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: 0 var(--space-2) var(--space-2);
  border-top: 1px solid var(--p-content-border-color);
  padding-top: var(--space-2);
}

.form-grid {
  grid-template-columns: 1fr;
  gap: var(--space-2);
}

.field {
  label {
    font-size: var(--font-size-xs);
    color: var(--p-text-muted-color);
  }
}

.row-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
