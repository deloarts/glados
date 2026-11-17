<script setup lang="ts">
// A titled list of production order cards with an empty state. The parent
// builds each card's bindings, so this component knows nothing about the
// queue store, dialogs or permissions.
import ProductionOrderCard from '../../queue/components/ProductionOrderCard.vue'

import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'
import type { LotResponse } from '../../types/productionLotsResponse'

defineProps<{
  title: string
  orders: ProductionOrderResponse[]
  emptyMessage: string
  cardBindings: (order: ProductionOrderResponse) => {
    order: ProductionOrderResponse
    canWrite: boolean
    canManage: boolean
    draggable: boolean
    processMethod: string | null
    lot: LotResponse | null
    onStart: (order: ProductionOrderResponse) => void
    onPause: (order: ProductionOrderResponse) => void
    onSplit: (order: ProductionOrderResponse) => void
    onMerge: (order: ProductionOrderResponse) => void
    onComplete: (order: ProductionOrderResponse) => void
    onCancel: (order: ProductionOrderResponse) => void
    onTogglePin: (order: ProductionOrderResponse) => void
  }
}>()
</script>

<template>
  <Panel :header="title">
    <!-- The scroll card scrolls this class, so a long queue scrolls instead of
         clipping. -->
    <div class="card-scroll-body">
      <div v-if="orders.length === 0" class="empty-note">{{ emptyMessage }}</div>
      <div v-else class="order-list">
        <ProductionOrderCard v-for="order in orders" :key="order.id" v-bind="cardBindings(order)" />
      </div>
    </div>
  </Panel>
</template>

<style scoped lang="scss">
.empty-note {
  padding: var(--space-2) 0;
}

.order-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
</style>
