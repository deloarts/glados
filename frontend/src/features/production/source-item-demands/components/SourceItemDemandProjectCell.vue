<script setup lang="ts">
// The Project cell of the source item demands table: the project number,
// which opens the project, its customer and its description.
import type { SourceItemDemandResponse } from '@/features/source-items'

defineProps<{
  demand: SourceItemDemandResponse
}>()
</script>

<template>
  <div class="project-cell">
    <RouterLink class="project-link" :to="`/workspace/projects/${demand.project_id}`">{{
      demand.project_number
    }}</RouterLink>
    <span class="project-customer">{{ demand.project_customer }}</span>
    <span class="project-description">{{ demand.project_description }}</span>
  </div>
</template>

<style scoped lang="scss">
.project-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
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

.project-customer {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.project-description {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  max-width: 11rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
