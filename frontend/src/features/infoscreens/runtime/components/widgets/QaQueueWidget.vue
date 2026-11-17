<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { toDayKey } from '@/core/utils/dates'

import type { InfoscreenQaRow, WidgetConfigOf, WidgetDataOf } from '../../types/infoscreenFeed'
import { formatDay, formatInstantTime, joinParts, statusLabel } from '../../utils/infoscreenFormat'
import RowThumbnail from './RowThumbnail.vue'
import WidgetFrame from './WidgetFrame.vue'

defineProps<{
  config: WidgetConfigOf<'qa_queue'>
  data: WidgetDataOf<'qa_queue'>
}>()

const { t, te } = useI18n()

// Waiting since today shows the time, anything older its day.
function sinceLabel(task: InfoscreenQaRow): string | null {
  if (!task.since) return null
  const today = toDayKey(new Date().toISOString())
  const when =
    toDayKey(task.since) === today ? formatInstantTime(task.since) : formatDay(task.since)
  return when ? t('infoscreenRuntime.widgets.qaQueue.since', { time: when }) : null
}
</script>

<template>
  <WidgetFrame
    :title="config.title || t('infoscreenRuntime.widgets.qaQueue.title')"
    :count="data.tasks.length"
  >
    <ul v-if="data.tasks.length > 0" class="qa-rows">
      <li v-for="task in data.tasks" :key="task.task_id" class="qa-row" data-testid="qa-row">
        <RowThumbnail :url="task.thumbnail_url" />
        <div class="qa-row-main">
          <span class="qa-row-number">{{ task.lot_number ?? task.part_number }}</span>
          <span class="qa-row-detail">{{ joinParts(task.part_number, task.item_name) }}</span>
        </div>
        <div class="qa-row-side">
          <span>{{ statusLabel(t, te, task.status, ['production.lots.orderStatus']) }}</span>
          <span class="qa-row-since">{{ sinceLabel(task) }}</span>
        </div>
      </li>
    </ul>
    <p v-else class="widget-empty">{{ t('infoscreenRuntime.widgets.qaQueue.empty') }}</p>
  </WidgetFrame>
</template>

<style scoped lang="scss">
.qa-rows {
  list-style: none;
  margin: 0;
  padding: 0;
}

.qa-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1em;
  padding: 0.35em 0;
  border-bottom: 1px solid var(--p-content-border-color);
}

.qa-row-main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.qa-row-number {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.qa-row-detail,
.qa-row-since {
  font-size: 0.8em;
  color: var(--p-text-muted-color);
}

.qa-row-detail {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.qa-row-side {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.widget-empty {
  margin: 0;
  color: var(--p-text-muted-color);
}
</style>
