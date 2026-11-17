<script setup lang="ts">
// Project of an order item: its number linking to the project, the customer
// and a clipped description.
import type { OrderItemResponse } from '../types/ordersResponse'

defineProps<{
  item: OrderItemResponse
}>()
</script>

<template>
  <div class="item-cell">
    <RouterLink class="project-number project-link" :to="`/workspace/projects/${item.project_id}`">{{
      item.project_number
    }}</RouterLink>
    <span class="project-customer">{{ item.project_customer }}</span>
    <span class="project-description">{{ item.project_description }}</span>
  </div>
</template>

<style scoped lang="scss">
.item-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 10rem;
}

.project-number {
  font-weight: 600;
}

.project-link {
  color: inherit;
  text-decoration: none;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}

.project-customer {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
}

.project-description {
  display: block;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
  max-width: 12rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
