<script setup lang="ts">
// Read-only item cell of an order item row, picking the cell that matches
// the line type. Opening a made or bought item is emitted.
import OrderItemCellBought from './OrderItemCellBought.vue'
import OrderItemCellVirtual from './OrderItemCellVirtual.vue'
import OrderItemCellMade from './OrderItemCellMade.vue'
import OrderItemCellSource from './OrderItemCellSource.vue'

import type { OrderItemResponse } from '../../types/ordersResponse'

defineProps<{
  item: OrderItemResponse
}>()

const emit = defineEmits<{
  openMadeItem: [id: number]
  openBoughtItem: [id: number]
}>()
</script>

<template>
  <OrderItemCellMade
    v-if="item.line_type === 'MADE'"
    :item="item"
    @open-item="(id) => emit('openMadeItem', id)"
  />
  <OrderItemCellSource v-else-if="item.line_type === 'SOURCE'" :item="item" />
  <OrderItemCellVirtual v-else-if="item.line_type === 'VIRTUAL'" :item="item" />
  <OrderItemCellBought v-else :item="item" @open-item="(id) => emit('openBoughtItem', id)" />
</template>
