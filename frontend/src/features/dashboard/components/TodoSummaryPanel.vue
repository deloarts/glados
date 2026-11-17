<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import PanelLoading from './PanelLoading.vue'

import { TodoTaskRow } from '@/features/todo'
import type { TodoTask } from '@/features/todo'

const props = defineProps<{
  overdue: TodoTask[]
  today: TodoTask[]
  loading: boolean
}>()

const { t } = useI18n()
const router = useRouter()

const MAX_ROWS = 6

// Only what needs doing now; the full page carries the rest.
const rows = computed(() => [...props.overdue, ...props.today].slice(0, MAX_ROWS))
const totalDueNow = computed(() => props.overdue.length + props.today.length)
</script>

<template>
  <div class="card todo-summary-panel">
    <div class="panel-title">
      <i class="mdi mdi-checkbox-marked-outline" aria-hidden="true" />
      <span>{{ t('todo.title') }}</span>
      <Button
        :label="t('todo.viewAll')"
        size="small"
        variant="text"
        class="view-all-btn"
        @click="router.push('/todo')"
      />
    </div>

    <PanelLoading v-if="loading && rows.length === 0" class="panel-loading" />

    <div v-else-if="rows.length === 0" class="panel-empty">
      <i class="mdi mdi-check-circle-outline panel-empty-icon" aria-hidden="true" />
      <span>{{ t('todo.empty') }}</span>
    </div>

    <template v-else>
      <ul class="todo-summary-list">
        <TodoTaskRow v-for="task in rows" :key="task.id" :task="task" compact />
      </ul>
      <div v-if="totalDueNow > rows.length" class="todo-summary-more">
        {{ t('todo.andMore', { count: totalDueNow - rows.length }) }}
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.todo-summary-panel {
  gap: var(--space-2);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);

  .view-all-btn {
    margin-left: auto;
    font-size: var(--font-size-xs);
    padding: var(--space-1) var(--space-2);
  }
}

.panel-loading,
.panel-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--p-text-muted-color);
  padding: var(--space-5) 0;
  flex: 1 1 auto;
}

.panel-empty-icon {
  font-size: var(--font-size-2xl);
  color: var(--p-green-500);
}

.todo-summary-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  // min-height: 0 lets this shrink below its content inside the flex card,
  // so an over-long list scrolls here instead of stretching the tile.
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

.todo-summary-more {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  text-align: center;
  padding-top: var(--space-1);
}
</style>
