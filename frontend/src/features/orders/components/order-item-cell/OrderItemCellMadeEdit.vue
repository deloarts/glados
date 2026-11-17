<script setup lang="ts">
import type { OrderItemResponse } from '../../types/ordersResponse'

// A MADE line's identity belongs to its catalogue entry, so it's shown but
// not editable here; rename the entry itself instead.
defineProps<{ item: OrderItemResponse }>()
</script>

<template>
  <div class="edit-item-cell">
    <span class="item-name">{{ item.item_article_name }}</span>
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
</style>
