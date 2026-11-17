<script setup lang="ts">
import type { OrderItemResponse } from '../../types/ordersResponse'

// A SOURCE line's identity belongs to its catalogue entry too, but showing
// name + spec + codes here (rather than just the name, as MADE does) lets
// the user editing the line still see what they're ordering against.
defineProps<{ item: OrderItemResponse }>()
</script>

<template>
  <div class="edit-item-cell">
    <span class="item-name">{{ item.item_article_name }}</span>
    <span v-if="item.item_specification" class="item-code">{{ item.item_specification }}</span>
    <span v-if="item.item_order_code_1" class="item-code">{{ item.item_order_code_1 }}</span>
    <span v-if="item.item_order_code_2" class="item-code">{{ item.item_order_code_2 }}</span>
  </div>
</template>

<style scoped lang="scss">
.edit-item-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.item-name {
  font-weight: 600;
}

.item-code {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
}
</style>
