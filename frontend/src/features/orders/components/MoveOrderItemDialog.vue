<script setup lang="ts">
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useOrdersStore } from '../stores/ordersStore'
import { moveTargetStatuses } from '../composables/useOrderItemActions'
import OrderSelect from './OrderSelect.vue'
import type { OrderItemResponse, OrderResponse } from '../types/ordersResponse'
import { formatUnit } from '@/shared/utils/units'

const props = defineProps<{
  visible: boolean
  item: OrderItemResponse | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const ordersStore = useOrdersStore()

const targetOrder = ref<OrderResponse | null>(null)
// Lists only the orders the backend accepts the line on for this user.
const { hasPermission } = usePermissions()
const targetStatuses = computed(() =>
  props.item ? moveTargetStatuses(props.item, hasPermission(Permission.MANAGE_ORDERS)) : undefined,
)
const { submitting: moving, errorMessage: error, run } = useSubmitAction()

const supplierDiffers = computed(
  () =>
    !!props.item && !!targetOrder.value && props.item.supplier_id !== targetOrder.value.supplier_id,
)
// A line that is ordered already went to its supplier: moving it to another
// supplier's order fixes a booking, and someone has to settle the first
// supplier, so the move waits for that confirmation.
const orderedElsewhere = computed(
  () =>
    supplierDiffers.value &&
    !!props.item &&
    props.item.status !== 'pending' &&
    props.item.status !== 'requested',
)
const settledWithSupplier = ref(false)

watch(
  () => props.visible,
  (val) => {
    if (val) {
      targetOrder.value = null
      error.value = null
      settledWithSupplier.value = false
    }
  },
)

async function confirm(): Promise<void> {
  const item = props.item
  const target = targetOrder.value
  if (!item || !target) return
  await run(async () => {
    await ordersStore.moveItem(item, target)
    emit('update:visible', false)
  }, t('orders.items.errors.unknown'))
}
</script>

<template>
  <Dialog
    :visible="visible"
    @update:visible="emit('update:visible', $event)"
    modal
    :header="t('orders.actions.moveItemTitle')"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <div class="move-item-body">
      <div class="item-summary">
        <span class="item-name">{{ item?.item_article_name }}</span>
        <span class="item-meta"
          >{{ item?.quantity }} {{ formatUnit(item?.unit) }} · {{ item?.project_number }}</span
        >
      </div>

      <div class="field">
        <label :id="`${uid}-move-item-select-order-label`" :for="`${uid}-move-item-select-order`">
          {{ t('orders.actions.moveItemSelectOrder') }}
        </label>
        <OrderSelect
          v-model="targetOrder"
          class="target-order-select"
          :input-id="`${uid}-move-item-select-order`"
          :aria-labelledby="`${uid}-move-item-select-order-label`"
          :exclude="item?.order_id"
          :statuses="targetStatuses"
        />
      </div>

      <Message v-if="supplierDiffers" severity="warn" :closable="false">
        {{ t('orders.actions.moveItemSupplierWarning') }}
      </Message>

      <div v-if="orderedElsewhere" class="ordered-elsewhere">
        <Message severity="warn" :closable="false">
          {{ t('orders.actions.moveItemOrderedWarning', { supplier: item?.supplier_name }) }}
        </Message>
        <div class="checkbox-field">
          <Checkbox v-model="settledWithSupplier" input-id="move-item-settled" :binary="true" />
          <label for="move-item-settled">
            {{ t('orders.actions.moveItemOrderedConfirm', { supplier: item?.supplier_name }) }}
          </label>
        </div>
      </div>

      <p class="confirm-text">{{ t('orders.actions.moveItemConfirm') }}</p>

      <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
    </div>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="moving"
        @click="emit('update:visible', false)"
      />
      <Button
        :label="t('orders.actions.moveItem')"
        icon="mdi mdi-folder-move-outline"
        severity="warn"
        :loading="moving"
        data-testid="move-item-confirm"
        :disabled="!targetOrder || (orderedElsewhere && !settledWithSupplier)"
        @click="confirm"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.move-item-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.ordered-elsewhere {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.checkbox-field {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.item-summary {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  background: var(--p-surface-50);
  border-radius: var(--p-content-border-radius);
}

.p-dark .item-summary {
  background: var(--p-surface-800);
}

.item-name {
  font-weight: 600;
}

.item-meta {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.field {
  gap: var(--space-2);

  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.target-order-select {
  width: 100%;
}

.confirm-text {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
