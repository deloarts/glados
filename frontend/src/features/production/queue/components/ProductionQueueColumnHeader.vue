<script setup lang="ts">
// Header of one production queue board column: its name, a subtitle that
// depends on the column kind, the fabrication methods it can run and the
// number of orders it currently shows.
import { useI18n } from 'vue-i18n'

import type { BoardColumn } from '../composables/useQueueBoardColumns'
import LabelTag from '@/shared/components/labels/LabelTag.vue'

defineProps<{
  column: BoardColumn
  count: number
}>()

const { t } = useI18n()
</script>

<template>
  <div class="column-header">
    <div class="column-title-group">
      <!-- Only real machines have a detail page to link to. -->
      <RouterLink
        v-if="column.kind === 'machine'"
        :to="`/production/machines/${column.id}`"
        class="column-title column-title-link"
        >{{ column.internal_name }}</RouterLink
      >
      <span v-else class="column-title">{{ column.internal_name }}</span>
      <span v-if="column.kind === 'machine'" class="column-subtitle"
        >{{ column.vendor }} {{ column.model }}</span
      >
      <span v-else-if="column.kind === 'pool'" class="column-subtitle">{{
        t('productionQueue.board.poolMachineCount', { count: column.poolMachineCount })
      }}</span>
      <span v-else-if="column.kind === 'unassigned'" class="column-subtitle">{{
        t('productionQueue.board.noMachineSubtitle')
      }}</span>
      <span v-else class="column-subtitle"></span>
      <div v-if="column.capabilities.length > 0" class="column-capabilities">
        <LabelTag
          v-for="method in column.capabilities"
          :key="method.id"
          :label="method"
        />
      </div>
    </div>
    <span class="column-count">{{ count }}</span>
  </div>
</template>

<style scoped lang="scss">
.column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.column-title-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

// Keeps the heading's plain look against the global link colour; only the
// hover underline shows it is clickable.
.column-title-link {
  color: inherit;
  text-decoration: none;

  &:hover {
    text-decoration: underline;
  }
}

.column-subtitle {
  font-size: var(--font-size-xs);
  font-weight: 400;
  color: var(--p-text-muted-color);
  height: 1.5rem;
}

.column-capabilities {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin-top: var(--space-1);

  :deep(.p-tag) {
    font-size: var(--font-size-xs);
    padding: var(--space-1) var(--space-2);
  }
}

.column-count {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  background: var(--p-content-background);
  border-radius: 999px;
  padding: var(--space-1) var(--space-2);
}
</style>
