<script setup lang="ts">
import { ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import OrderSelect from './OrderSelect.vue'
import OrderCreateForm from './OrderCreateForm.vue'
import OrderItemCreateForm from './OrderItemCreateForm.vue'

import type { OrderResponse } from '../types/ordersResponse'
import type { BoughtItemResponse } from '@/features/bought-items'

defineProps<{
  item: BoughtItemResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()

const selectedOrder = ref<OrderResponse | null>(null)
const showCreateOrder = ref(false)
const showAddItem = ref(false)

watch(visible, (isVisible) => {
  if (!isVisible) return
  selectedOrder.value = null
})

function onContinue(): void {
  if (!selectedOrder.value) return
  visible.value = false
  showAddItem.value = true
}

function onOrderCreated(order: OrderResponse): void {
  selectedOrder.value = order
  visible.value = false
  showAddItem.value = true
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      item
        ? `${t('boughtItems.catalogue.addToOrder.title')}, ${item.article_name}`
        : t('boughtItems.catalogue.addToOrder.title')
    "
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <div class="picker">
      <div class="field">
        <label :id="`${uid}-select-order-label`" :for="`${uid}-select-order`">
          {{ t('boughtItems.catalogue.addToOrder.selectOrder') }}
        </label>
        <OrderSelect
          v-model="selectedOrder"
          :input-id="`${uid}-select-order`"
          :aria-labelledby="`${uid}-select-order-label`"
          fluid
        />
      </div>

      <Divider align="center">
        <span class="divider-label">{{ t('common.or') }}</span>
      </Divider>

      <Button
        :label="t('boughtItems.catalogue.addToOrder.createOrder')"
        icon="mdi mdi-plus"
        severity="secondary"
        outlined
        fluid
        @click="showCreateOrder = true"
      />
    </div>

    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" outlined @click="visible = false" />
      <Button :label="t('common.continue')" :disabled="!selectedOrder" @click="onContinue" />
    </template>
  </Dialog>

  <OrderCreateForm
    v-model:visible="showCreateOrder"
    :preset-supplier-id="item?.manufacturer_id"
    @created="onOrderCreated"
  />

  <OrderItemCreateForm
    v-if="selectedOrder"
    v-model:visible="showAddItem"
    :order-id="selectedOrder.id"
    :supplier-id="selectedOrder.supplier_id"
    :preset-item="item"
  />
</template>

<style scoped lang="scss">
.picker {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.divider-label {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
