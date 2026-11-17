<script setup lang="ts">
import { extractApiError } from '@/core/utils/errors'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { HelpDrawer } from '@/shared/help'

import { useSourceItemsAllocationsStore } from '../stores/sourceItemsAllocationsStore'
import { OrderSelect, createOrderItem } from '@/features/orders'

import type { OrderItemResponse, OrderResponse, OrderItemCreateRequest } from '@/features/orders'
import { formatUnit, unitsDiffer } from '@/shared/utils/units'
import UnitMismatchWarning from '@/shared/components/demands/UnitMismatchWarning.vue'
import type { SourceItemAllocationResponse } from '@/features/source-items'

const props = defineProps<{
  demandId: number | null
  demandUnit: string
  boughtItemId: number | null
  sourceItemId: number | null
  projectId: number | null
  itemArticleName: string | null
  itemOrderCode: string | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  changed: []
}>()

const { t } = useI18n()
const { toastOnError } = useErrorToast()
const allocationsStore = useSourceItemsAllocationsStore()

const errorMessage = ref<string | null>(null)
const explainVisible = ref(false)
const newOrderQuantity = ref<number | null>(null)
const newStockQuantity = ref<number | null>(null)
const substituteReason = ref('')
const workingQuantities = reactive<Record<string, number>>({})

const selectedOrder = ref<OrderResponse | null>(null)
const selectedOrderItem = ref<OrderItemResponse | null>(null)

// Creates a new order item on the selected order when it has no line for
// this material.
const creatingOrderItem = ref(false)
const newItemQuantity = ref<number | null>(null)

const loading = computed(() => allocationsStore.loadingAllocations)
const saving = computed(() => allocationsStore.savingAllocation)

const allocations = computed<SourceItemAllocationResponse[]>(() =>
  props.demandId !== null ? allocationsStore.getAllocations(props.demandId) : [],
)
const stockAllocation = computed(() => allocations.value.find((a) => a.source === 'stock'))

// Every source line of the order is eligible, since source materials can be
// substituted; a bought item must match exactly. See the substitution rule
// in docs/reference/domain-rules.md.
function matchesMaterial(item: OrderItemResponse): boolean {
  if (props.boughtItemId !== null) return item.bought_item_id === props.boughtItemId
  if (props.sourceItemId !== null) return item.source_item_id !== null
  return false
}

// A line the demand is already allocated to is changed in its row above.
const allocatedOrderItemIds = computed(
  () => new Set(allocations.value.map((a) => a.order_item_id).filter((id) => id !== null)),
)
const orderItemOptions = computed<OrderItemResponse[]>(
  () =>
    selectedOrder.value?.items?.filter(
      (i) => matchesMaterial(i) && !allocatedOrderItemIds.value.has(i.id),
    ) ?? [],
)

const isSubstitute = computed(
  () =>
    !!selectedOrderItem.value &&
    props.sourceItemId != null &&
    selectedOrderItem.value.source_item_id !== props.sourceItemId,
)

const canAddOrderAllocation = computed(
  () => !!selectedOrderItem.value && !!newOrderQuantity.value && newOrderQuantity.value > 0,
)
const canAddStockAllocation = computed(() => !!newStockQuantity.value && newStockQuantity.value > 0)
const canCreateOrderItem = computed(
  () => !!selectedOrder.value && !!newItemQuantity.value && newItemQuantity.value > 0,
)

function rowKey(row: SourceItemAllocationResponse): string {
  return row.source === 'stock' ? 'stock' : `order-${row.order_item_id}`
}

function rowQuantity(row: SourceItemAllocationResponse): number {
  return workingQuantities[rowKey(row)] ?? row.quantity
}

function setRowQuantity(row: SourceItemAllocationResponse, value: number | null): void {
  workingQuantities[rowKey(row)] = value ?? row.quantity
}

function orderItemOptionLabel(i: OrderItemResponse): string {
  const detail = i.item_specification || i.item_order_code_1
  const article = detail ? `${i.item_article_name} - ${detail}` : i.item_article_name
  return `${article} (${i.quantity} ${formatUnit(i.unit)}, ${t(`orders.items.status.${i.status}`)}, ${i.project_number})`
}

function rowLabel(row: SourceItemAllocationResponse): string {
  if (row.source === 'stock') return t('sourceItems.demands.allocationsDialog.sourceStock')
  if (row.order_number) {
    return `${row.order_number} (${row.order_supplier_name})`
  }
  return t('sourceItems.demands.allocationsDialog.orderItemLabel', { id: row.order_item_id })
}

watch(selectedOrder, () => {
  selectedOrderItem.value = null
  creatingOrderItem.value = false
  newItemQuantity.value = null
  substituteReason.value = ''
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
      creatingOrderItem.value = false
      newItemQuantity.value = null
      Object.keys(workingQuantities).forEach((key) => delete workingQuantities[key])
      allocationsStore.fetchAllocations(demandId).catch(toastOnError())
    }
  },
)

async function saveRow(row: SourceItemAllocationResponse): Promise<void> {
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
      extractApiError(e) ?? t('sourceItems.demands.allocationsDialog.errors.unknown')
  }
}

async function deleteRow(row: SourceItemAllocationResponse): Promise<void> {
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
      extractApiError(e) ?? t('sourceItems.demands.allocationsDialog.errors.unknown')
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
      substitute_source_item_id: isSubstitute.value
        ? selectedOrderItem.value.source_item_id
        : null,
      substitute_reason: isSubstitute.value ? substituteReason.value.trim() || null : null,
    })
    selectedOrder.value = null
    selectedOrderItem.value = null
    newOrderQuantity.value = null
    substituteReason.value = ''
    emit('changed')
  } catch (e) {
    errorMessage.value =
      extractApiError(e) ?? t('sourceItems.demands.allocationsDialog.errors.unknown')
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
      extractApiError(e) ?? t('sourceItems.demands.allocationsDialog.errors.unknown')
  }
}

// Creates an order item for the demand's own material and allocates the
// demand against it.
async function createOrderItemAndAllocate(): Promise<void> {
  if (
    props.demandId === null ||
    !selectedOrder.value ||
    !newItemQuantity.value ||
    props.projectId === null
  ) {
    return
  }

  errorMessage.value = null

  try {
    // A Pick of the real request, so a key rename fails type-checking.
    const materialRef: Pick<OrderItemCreateRequest, 'bought_item_id' | 'source_item_id'> =
      props.boughtItemId !== null
        ? { bought_item_id: props.boughtItemId }
        : { source_item_id: props.sourceItemId }
    const created = await createOrderItem(selectedOrder.value.id, {
      ...materialRef,
      supplier_id: selectedOrder.value.supplier_id,
      project_id: props.projectId,
      quantity: newItemQuantity.value,
      unit: props.demandUnit,
      items_per_unit: 1,
    })
    await allocationsStore.createAllocation({
      demand_item_id: props.demandId,
      order_item_id: created.id,
      quantity: Math.min(newItemQuantity.value, created.quantity),
    })
    selectedOrder.value = null
    creatingOrderItem.value = false
    newItemQuantity.value = null
    emit('changed')
  } catch (e) {
    errorMessage.value =
      extractApiError(e) ?? t('sourceItems.demands.allocationsDialog.errors.unknown')
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: 'var(--dialog-width-lg)' }">
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{ t('sourceItems.demands.allocationsDialog.title', { id: demandId }) }}</span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('sourceItems.demands.allocationsDialog.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('sourceItems.demands.allocationsDialog.explain')"
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
                <i
                  v-if="row.substitute_source_item_id"
                  class="mdi mdi-swap-horizontal alloc-substitute-icon"
                  v-tooltip="
                    row.substitute_reason ||
                    t('sourceItems.demands.substitution.tooltip')
                  "
                  aria-hidden="true"
                />
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
                    t('sourceItems.demands.allocationsDialog.orderedQty', {
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
          {{ t('sourceItems.demands.allocationsDialog.empty') }}
        </div>

        <Divider />

        <div class="alloc-add-title">
          {{ t('sourceItems.demands.allocationsDialog.addOrderAllocation') }}
        </div>
        <div class="alloc-add-row">
          <OrderSelect
            v-model="selectedOrder"
            any-status
            :aria-label="t('sourceItems.demands.allocationsDialog.selectOrderPlaceholder')"
            :placeholder="t('sourceItems.demands.allocationsDialog.selectOrderPlaceholder')"
            size="small"
            class="alloc-order-select"
          />
        </div>

        <template v-if="selectedOrder && !creatingOrderItem">
          <div class="alloc-add-row">
            <Select
              v-model="selectedOrderItem"
              :aria-label="t('sourceItems.demands.allocationsDialog.selectOrderItemPlaceholder')"
              :options="orderItemOptions"
              :option-label="orderItemOptionLabel"
              :placeholder="
                orderItemOptions.length === 0
                  ? t('sourceItems.demands.allocationsDialog.noMatchingOrderItems')
                  : t('sourceItems.demands.allocationsDialog.selectOrderItemPlaceholder')
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
          <div v-if="selectedOrderItem" class="alloc-add-row">
            <InputNumber
              class="row-input"
              v-model="newOrderQuantity"
              :min="0.001"
              :max-fraction-digits="3"
              :placeholder="t('sourceItems.demands.allocationsDialog.quantityPlaceholder')"
              size="small"
            />
            <Button
              :label="t('sourceItems.demands.allocationsDialog.add')"
              icon="mdi mdi-plus"
              size="small"
              :disabled="!canAddOrderAllocation"
              :loading="saving"
              @click="addOrderAllocation"
            />
          </div>

          <div v-else-if="orderItemOptions.length === 0" class="alloc-add-row">
            <Button
              :label="t('sourceItems.demands.allocationsDialog.createOrderItem')"
              icon="mdi mdi-plus-box"
              severity="secondary"
              outlined
              size="small"
              @click="creatingOrderItem = true"
            />
          </div>

          <div v-if="isSubstitute" class="alloc-add-row alloc-substitute-row">
            <i class="mdi mdi-swap-horizontal" aria-hidden="true" />
            <span class="alloc-substitute-warning">
              {{ t('sourceItems.demands.allocationsDialog.substituteWarning') }}
            </span>
            <InputText
              v-model="substituteReason"
              :placeholder="t('sourceItems.demands.procure.substituteReason')"
              size="small"
              class="alloc-order-select"
            />
          </div>
        </template>

        <template v-if="selectedOrder && creatingOrderItem">
          <Message severity="info" :closable="false" class="alloc-note">
            {{ t('sourceItems.demands.allocationsDialog.createOrderItemNote') }}
          </Message>
          <div class="alloc-add-row">
            <InputNumber
              class="row-input"
              v-model="newItemQuantity"
              :min="0.001"
              :max-fraction-digits="3"
              :placeholder="t('sourceItems.demands.allocationsDialog.quantityPlaceholder')"
              size="small"
            />
            <Button
              :label="t('sourceItems.demands.allocationsDialog.createAndAllocate')"
              icon="mdi mdi-cart-plus"
              size="small"
              :disabled="!canCreateOrderItem"
              :loading="saving"
              @click="createOrderItemAndAllocate"
            />
            <Button
              icon="mdi mdi-close"
              severity="secondary"
              text
              size="small"
              :aria-label="t('common.cancel')"
              @click="creatingOrderItem = false"
            />
          </div>
        </template>

        <template v-if="!stockAllocation">
          <div class="alloc-add-title">
            {{ t('sourceItems.demands.allocationsDialog.addStockAllocation') }}
          </div>
          <div class="alloc-add-row">
            <InputNumber
              class="row-input"
              v-model="newStockQuantity"
              :min="0.001"
              :max-fraction-digits="3"
              :placeholder="t('sourceItems.demands.allocationsDialog.quantityPlaceholder')"
              size="small"
            />
            <Button
              :label="t('sourceItems.demands.allocationsDialog.add')"
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

.alloc-substitute-icon {
  padding-left: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--p-primary-color);
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
