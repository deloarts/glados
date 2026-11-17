<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { formatISODate } from '@/core/utils/dates'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import type { TodoTask } from '../types/todoTask'

const props = defineProps<{ task: TodoTask; compact?: boolean }>()

const { t } = useI18n()
const router = useRouter()
const { openLotDetail } = useLotDetail()

function onClick(): void {
  if (props.task.lotId !== undefined) {
    openLotDetail(props.task.lotId)
  } else {
    void router.push(props.task.route)
  }
}

const TASK_ICONS: Record<string, string> = {
  collect_pickup: 'mdi mdi-package-variant-closed',
  confirm_pickup: 'mdi mdi-phone-outline',
  chase_delivery: 'mdi mdi-truck-alert-outline',
  chase_partial_delivery: 'mdi mdi-package-variant',
  submit_order: 'mdi mdi-file-send-outline',
  order_demand: 'mdi mdi-cart-plus',
  start_production_order: 'mdi mdi-play-circle-outline',
  production_conflict: 'mdi mdi-alert-outline',
  chase_raw_material: 'mdi mdi-cube-outline',
  plan_lot: 'mdi mdi-calendar-edit',
  resume_lot: 'mdi mdi-pause-circle-outline',
  meeting_todo: 'mdi mdi-account-group-outline',
}

const icon = computed(() => TASK_ICONS[props.task.kind] ?? 'mdi mdi-checkbox-blank-circle-outline')
const dueLabel = computed(() =>
  props.task.dueDate ? formatISODate(props.task.dueDate.toISOString()) : '',
)
</script>

<template>
  <li>
    <button
      type="button"
      class="todo-row"
      :class="[`todo-row--${task.bucket}`, { 'todo-row--compact': compact }]"
      @click="onClick"
    >
      <i class="todo-row-icon" :class="icon" aria-hidden="true" />
      <div class="todo-row-body">
        <span class="todo-row-title">
          {{ t(task.titleKey, task.titleParams) }}
          <i v-if="task.highPriority" class="mdi mdi-flag todo-row-flag" aria-hidden="true" />
        </span>
        <span class="todo-row-subtitle">{{ t(task.subtitleKey, task.subtitleParams) }}</span>
      </div>
      <span v-if="dueLabel" class="todo-row-due">{{ dueLabel }}</span>
    </button>
  </li>
</template>

<style scoped lang="scss">
.todo-row {
  display: flex;
  align-items: center;
  width: 100%;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--p-content-border-radius);
  border: none;
  border-left: 3px solid transparent;
  background: none;
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.15s;

  &:hover {
    background-color: var(--p-content-hover-background);
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: -2px;
  }
}

.todo-row--overdue {
  border-left-color: var(--p-red-500);
}
.todo-row--today {
  border-left-color: var(--p-orange-500);
}
.todo-row--week {
  border-left-color: var(--p-blue-500);
}
.todo-row--blockers {
  border-left-color: var(--p-purple-500);
}

.todo-row-icon {
  flex-shrink: 0;
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

.todo-row-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1 1 auto;
}

.todo-row-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo-row-flag {
  color: var(--p-red-500);
  font-size: var(--font-size-sm);
  margin-left: var(--space-1);
}

.todo-row-subtitle {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo-row-due {
  flex-shrink: 0;
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.todo-row--compact {
  padding: var(--space-2) var(--space-2);
}
</style>
