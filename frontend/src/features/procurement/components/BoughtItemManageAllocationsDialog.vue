<script setup lang="ts">
import { extractApiError } from '@/core/utils/errors'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { HelpDrawer } from '@/shared/help'

import { useBoughtItemsAllocationsStore } from '../stores/boughtItemsAllocationsStore'
import { OrderSelect } from '@/features/orders'

import type { OrderItemResponse, OrderResponse } from '@/features/orders'
import { formatUnit, unitsDiffer } from '@/shared/utils/units'
import UnitMismatchWarning from '@/shared/components/demands/UnitMismatchWarning.vue'
import type { AllocationResponse } from '@/features/bought-items'

const props = defineProps<{
  demandId: number | null
  demandUnit: string
  itemId: number | null
  itemOrderCode: string | null
  itemArticleName: string | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  changed: []
}>()

const { t } = useI18n()
const { toastOnError } = useErrorToast()
const allocationsStore = useBoughtItemsAllocationsStore()

const errorMessage = ref<string | null>(null)
const explainVisible = ref(false)
const newOrderQuantity = ref<number | null>(null)
const newStockQuantity = ref<number | null>(null)
const substituteReason = ref('')
const workingQuantities = reactive<Record<string, number>>({})

const selectedOrder = ref<OrderResponse | null>(null)
const selectedOrderItem = ref<OrderItemResponse | null>(null)

const loading = computed(() => allocationsStore.loadingAllocations)
const saving = computed(() => allocationsStore.savingAllocation)

const allocations = computed<AllocationResponse[]>(() =>
  props.demandId !== null ? allocationsStore.getAllocations(props.demandId) : [],
)
const stockAllocation = computed(() => allocations.value.find((a) => a.source === 'stock'))

// Every item of the order is offered, since linking another item is a
// valid substitution, except the lines the demand is already allocated to,
// whose quantity is changed in their row above.
const allocatedOrderItemIds = computed(
  () => new Set(allocations.value.map((a) => a.order_item_id).filter((id) => id !== null)),
)
const orderItemOptions = computed<OrderItemResponse[]>(
  () => selectedOrder.value?.items?.filter((i) => !allocatedOrderItemIds.value.has(i.id)) ?? [],
)

// A different item id is always sent as a substitution, as the backend
// requires, but the warning and reason only appear when the article visibly
// differs.
const idsDiffer = computed(
  () =>
    !!selectedOrderItem.value &&
    props.itemId != null &&
    selectedOrderItem.value.bought_item_id !== props.itemId,
)
const isSubstitute = computed(
  () => idsDiffer.value && selectedOrderItem.value?.item_order_code_1 !== props.itemOrderCode,
)

const canAddOrderAllocation = computed(
  () => !!selectedOrderItem.value && !!newOrderQuantity.value && newOrderQuantity.value > 0,
)
const canAddStockAllocation = computed(() => !!newStockQuantity.value && newStockQuantity.value > 0)

function rowKey(row: AllocationResponse): string {
  return row.source === 'stock' ? 'stock' : `order-${row.order_item_id}`
}

function rowQuantity(row: AllocationResponse): number {
  return workingQuantities[rowKey(row)] ?? row.quantity
}

function setRowQuantity(row: AllocationResponse, value: number | null): void {
  workingQuantities[rowKey(row)] = value ?? row.quantity
}

function orderItemOptionLabel(i: OrderItemResponse): string {
  return `${i.item_order_code_1} (${i.quantity} ${formatUnit(i.unit)}, ${t(`orders.items.status.${i.status}`)}, ${i.project_number})`
}

function rowLabel(row: AllocationResponse): string {
  if (row.source === 'stock') return t('boughtItems.demands.allocationsDialog.sourceStock')
  if (row.order_number) {
    return `${row.order_number} (${row.order_supplier_name})`
  }
  return t('boughtItems.demands.allocationsDialog.orderItemLabel', { id: row.order_item_id })
}

watch(selectedOrder, () => {
  selectedOrderItem.value = null
})

watch(
  () => [visible.value, props.demandId] as const,
  ([isVisible, demandId]) => {
    if (isVisible && demandId !== null) {
      errorMessage.value = null
      newOrderQuantity.value = null
      newStockQuantity.value = null
      substituteReason.value = ''
      selectedOrder.value = null
      selectedOrderItem.value = null
      Object.keys(workingQuantities).forEach((key) => delete workingQuantities[key])
      allocationsStore.fetchAllocations(demandId).catch(toastOnError())
    }
  },
)

async function saveRow(row: AllocationResponse): Promise<void> {
  if (props.demandId === null) return

  errorMessage.value = null

  try {
    if (row.source === 'stock') {
      await allocationsStore.updateStockAllocation(props.demandId, rowQuantity(row))
    } else if (row.order_item_id !== null) {
      await allocationsStore.updateAllocation(props.demandId, row.order_item_id, rowQuantity(row))
    }
    emit('changed')
  } catch (e) {
    errorMessage.value =
      extractApiError(e) ?? t('boughtItems.demands.allocationsDialog.errors.unknown')
  }
}

async function deleteRow(row: AllocationResponse): Promise<void> {
  if (props.demandId === null) return

  errorMessage.value = null

  try {
    if (row.source === 'stock') {
      await allocationsStore.deleteStockAllocation(props.demandId)
    } else if (row.order_item_id !== null) {
      await allocationsStore.deleteAllocation(props.demandId, row.order_item_id)
    }
    emit('changed')
  } catch (e) {
    errorMessage.value =
      extractApiError(e) ?? t('boughtItems.demands.allocationsDialog.errors.unknown')
  }
}

async function addOrderAllocation(): Promise<void> {
  if (props.demandId === null || !selectedOrderItem.value || !newOrderQuantity.value) return

  errorMessage.value = null

  try {
    await allocationsStore.createAllocation({
      demand_item_id: props.demandId,
      order_item_id: selectedOrderItem.value.id,
      quantity: newOrderQuantity.value,
      ...(idsDiffer.value
        ? {
            substitute_item_id: selectedOrderItem.value.bought_item_id,
            substitute_reason: isSubstitute.value ? substituteReason.value.trim() || null : null,
          }
        : {}),
    })
    selectedOrder.value = null
    selectedOrderItem.value = null
    newOrderQuantity.value = null
    substituteReason.value = ''
    emit('changed')
  } catch (e) {
    errorMessage.value =
      extractApiError(e) ?? t('boughtItems.demands.allocationsDialog.errors.unknown')
  }
}

async function addStockAllocation(): Promise<void> {
  if (props.demandId === null || !newStockQuantity.value) return

  errorMessage.value = null

  try {
    await allocationsStore.updateStockAllocation(props.demandId, newStockQuantity.value)
    newStockQuantity.value = null
    emit('changed')
  } catch (e) {
    errorMessage.value =
      extractApiError(e) ?? t('boughtItems.demands.allocationsDialog.errors.unknown')
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: 'var(--dialog-width-lg)' }">
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{ t('boughtItems.demands.allocationsDialog.title', { id: demandId }) }}</span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('boughtItems.demands.allocationsDialog.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('boughtItems.demands.allocationsDialog.explain')"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <div class="alloc-item-detail">
      <span class="alloc-row-item-name">{{ props.itemArticleName }}</span>
      <span class="alloc-row-item-code">{{ props.itemOrderCode }}</span>
    </div>

    <div class="alloc-dialog">
      <div v-if="loading" class="alloc-loading">
        <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
      </div>
      <template v-else>
        <div v-if="allocations.length" class="alloc-rows">
          <div v-for="row in allocations" :key="rowKey(row)" class="alloc-row">
            <div class="alloc-row-item">
              <div>
                <Tag :value="rowLabel(row)" :severity="row.source === 'stock' ? 'help' : 'info'" />
              </div>
              <div class="allow-row-item-controls">
                <InputNumber
                  :model-value="rowQuantity(row)"
                  :min="0.001"
                  :max-fraction-digits="3"
                  size="small"
                  @update:model-value="(v: number | null) => setRowQuantity(row, v)"
                  style="width: 4rem"
                  fluid
                />
                <span class="alloc-unit">{{ formatUnit(demandUnit) }}</span>
                <span v-if="row.order_item_quantity != null" class="alloc-row-required">
                  {{
                    t('boughtItems.demands.allocationsDialog.orderedQty', {
                      quantity: row.order_item_quantity,
                    })
                  }}
                </span>
                <div class="alloc-row-actions">
                  <Button
                    icon="mdi mdi-check"
                    size="small"
                    severity="success"
                    text
                    rounded
                    :loading="saving"
                    v-tooltip.focus="t('common.save')"
                    :aria-label="t('common.save')"
                    @click="saveRow(row)"
                  />
                  <Button
                    icon="mdi mdi-delete-outline"
                    size="small"
                    severity="danger"
                    text
                    rounded
                    :loading="saving"
                    v-tooltip.focus="t('common.delete')"
                    :aria-label="t('common.delete')"
                    @click="deleteRow(row)"
                  />
                </div>
              </div>
            </div>
            <UnitMismatchWarning
              v-if="row.unit_mismatch && row.order_item_unit"
              :demand-unit="demandUnit"
              :line-unit="row.order_item_unit"
            />
          </div>
        </div>
        <div v-else class="alloc-empty">
          {{ t('boughtItems.demands.allocationsDialog.empty') }}
        </div>

        <Divider />

        <div class="alloc-add-title">
          {{ t('boughtItems.demands.allocationsDialog.addOrderAllocation') }}
        </div>
        <Message severity="info" :closable="false" class="alloc-note">
          {{ t('boughtItems.demands.allocationsDialog.manualLinkNote') }}
        </Message>
        <div class="alloc-add-row">
          <OrderSelect
            v-model="selectedOrder"
            any-status
            :aria-label="t('boughtItems.demands.allocationsDialog.selectOrderPlaceholder')"
            :placeholder="t('boughtItems.demands.allocationsDialog.selectOrderPlaceholder')"
            size="small"
            class="alloc-order-select"
          />
        </div>
        <div class="alloc-add-row">
          <Select
            v-model="selectedOrderItem"
            :aria-label="t('boughtItems.demands.allocationsDialog.selectOrderItemPlaceholder')"
            :options="orderItemOptions"
            :option-label="orderItemOptionLabel"
            :disabled="!selectedOrder"
            :placeholder="
              selectedOrder && orderItemOptions.length === 0
                ? t('boughtItems.demands.allocationsDialog.noOrderItems')
                : t('boughtItems.demands.allocationsDialog.selectOrderItemPlaceholder')
            "
            show-clear
            size="small"
            class="alloc-order-select"
          />
        </div>
        <UnitMismatchWarning
          v-if="selectedOrderItem && unitsDiffer(demandUnit, selectedOrderItem.unit)"
          :demand-unit="demandUnit"
          :line-unit="selectedOrderItem.unit"
        />
        <div class="alloc-add-row">
          <InputNumber
            class="row-input"
            v-model="newOrderQuantity"
            :min="0.001"
            :max-fraction-digits="3"
            :placeholder="t('boughtItems.demands.allocationsDialog.quantityPlaceholder')"
            size="small"
          />
          <Button
            :label="t('boughtItems.demands.allocationsDialog.add')"
            icon="mdi mdi-plus"
            size="small"
            :disabled="!canAddOrderAllocation"
            :loading="saving"
            @click="addOrderAllocation"
          />
        </div>

        <div v-if="isSubstitute" class="alloc-add-row alloc-substitute-row">
          <i class="mdi mdi-swap-horizontal" aria-hidden="true" />
          <span class="alloc-substitute-warning">
            {{ t('boughtItems.demands.allocationsDialog.substituteWarning') }}
          </span>
          <InputText
            v-model="substituteReason"
            :placeholder="t('boughtItems.demands.procure.substituteReason')"
            size="small"
            class="alloc-order-select"
          />
        </div>

        <template v-if="!stockAllocation">
          <div class="alloc-add-title">
            {{ t('boughtItems.demands.allocationsDialog.addStockAllocation') }}
          </div>
          <div class="alloc-add-row">
            <InputNumber
              class="row-input"
              v-model="newStockQuantity"
              :min="0.001"
              :max-fraction-digits="3"
              :placeholder="t('boughtItems.demands.allocationsDialog.quantityPlaceholder')"
              size="small"
            />
            <Button
              :label="t('boughtItems.demands.allocationsDialog.add')"
              icon="mdi mdi-plus"
              size="small"
              :disabled="!canAddStockAllocation"
              :loading="saving"
              @click="addStockAllocation"
            />
          </div>
        </template>
      </template>

      <Message v-if="errorMessage" severity="error" :closable="false" class="alloc-error">
        {{ errorMessage }}
      </Message>
    </div>

    <template #footer>
      <Button :label="t('common.close')" severity="secondary" outlined @click="visible = false" />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="procurement/demand-allocations" />
</template>

<style scoped lang="scss">
.dialog-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.dialog-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.alloc-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.alloc-loading {
  display: flex;
  justify-content: center;
  padding: var(--space-4);
  color: var(--p-text-muted-color);
}

.alloc-empty {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
  padding: var(--space-2) 0;
}

.alloc-rows {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.alloc-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-2);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.alloc-row-item {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-2);
  align-items: left;
}

.allow-row-item-controls {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: var(--space-2);
}

.alloc-item-detail {
  display: flex;
  gap: var(--space-1);
  flex-direction: column;
  padding-bottom: var(--space-3);
  margin-bottom: var(--space-3);
  border-bottom: 1px solid var(--p-content-border-color);
}

.alloc-row-item-name {
  font-size: var(--font-size-sm);
  font-weight: 500;
}

.alloc-row-item-code {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.alloc-unit {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
  padding-left: var(--space-1);
}

.alloc-row-required {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  white-space: nowrap;
  padding-left: var(--space-1);
}

.alloc-row-actions {
  margin-left: auto;
  display: flex;
  white-space: nowrap;
}

.alloc-add-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--p-text-muted-color);
  margin-top: var(--space-1);
}

.alloc-add-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.alloc-order-select {
  flex: 1;
  min-width: 0;
}

.alloc-substitute-row {
  font-size: var(--font-size-sm);
  color: var(--p-orange-500);
}

.alloc-substitute-warning {
  white-space: nowrap;
}

.alloc-error {
  margin-top: var(--space-1);
}

.alloc-note {
  font-size: var(--font-size-sm);
}

.row-input {
  flex: 1;
}
</style>
