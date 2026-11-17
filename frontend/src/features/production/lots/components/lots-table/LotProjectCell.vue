<script setup lang="ts">
import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

defineProps<{
  lot: LotSummaryResponse
}>()
</script>

<template>
  <div class="item-cell">
    <RouterLink class="project-link" :to="`/workspace/projects/${lot.project_id}`" @click.stop>{{
      lot.project_number
    }}</RouterLink>
    <span class="item-code">{{ lot.project_customer }}</span>
  </div>
</template>

<style scoped lang="scss">
.item-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.item-code {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.project-link {
  font-weight: 600;
  color: inherit;
  text-decoration: none;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}
</style>
