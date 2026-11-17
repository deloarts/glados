<script setup lang="ts">
// Average worked time per weekday with a bar scaled to the longest
// average, plus the average first in and last out per weekday and over the
// whole month. A table rather than a chart: seven rows with three numbers
// each read better as text, and the bar only adds the comparison.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { formatDuration } from '@/shared/utils/formatDuration'
import { shortWeekdayName } from '../utils/timeTrackingMonth'
import { averageDayBounds, formatMinutesOfDay, weekdayStats } from '../utils/timeTrackingStats'
import type { TimeTrackingDay } from '../types/timeTrackingTypes'

const props = defineProps<{
  /** Only the days the statistics count, see countedDays(). */
  days: TimeTrackingDay[]
}>()

const { t } = useI18n()

const rows = computed(() => weekdayStats(props.days).filter((row) => row.days > 0))
const bounds = computed(() => averageDayBounds(props.days))
const longest = computed(() =>
  Math.max(1, ...rows.value.map((row) => row.averageWorkedSeconds ?? 0)),
)

function timeOrDash(minutes: number | null): string {
  return minutes === null ? getEmptyPlaceholder() : formatMinutesOfDay(minutes)
}
</script>

<template>
  <div data-testid="time-tracking-weekday-stats">
    <EmptyState
      v-if="rows.length === 0"
      :message="t('timeTracking.stats.noData')"
      icon="mdi mdi-calendar-week"
    />
    <template v-else>
      <table class="tt-weekday-table">
        <thead>
          <tr>
            <th scope="col">{{ t('timeTracking.stats.weekday') }}</th>
            <th scope="col">{{ t('timeTracking.stats.averageWorked') }}</th>
            <th scope="col" class="num">{{ t('timeTracking.stats.averageFirstIn') }}</th>
            <th scope="col" class="num">{{ t('timeTracking.stats.averageLastOut') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.weekday">
            <th scope="row">
              {{ shortWeekdayName(row.weekday) }}
              <span class="tt-muted">({{ row.days }})</span>
            </th>
            <td>
              <div class="tt-meter">
                <span class="tt-meter-track" aria-hidden="true">
                  <span
                    class="tt-meter-bar"
                    :style="{ width: `${((row.averageWorkedSeconds ?? 0) / longest) * 100}%` }"
                  />
                </span>
                <span class="tt-meter-value">{{
                  row.averageWorkedSeconds === null
                    ? getEmptyPlaceholder()
                    : formatDuration(Math.round(row.averageWorkedSeconds))
                }}</span>
              </div>
            </td>
            <td class="num">{{ timeOrDash(row.averageFirstInMinutes) }}</td>
            <td class="num">{{ timeOrDash(row.averageLastOutMinutes) }}</td>
          </tr>
        </tbody>
      </table>
      <p class="tt-muted tt-bounds">
        {{
          t('timeTracking.stats.averageBounds', {
            firstIn: timeOrDash(bounds.firstInMinutes),
            lastOut: timeOrDash(bounds.lastOutMinutes),
          })
        }}
      </p>
    </template>
  </div>
</template>

<style scoped lang="scss">
.tt-weekday-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);

  th,
  td {
    padding: var(--space-1) var(--space-2);
    border-bottom: 1px solid var(--p-content-border-color);
    text-align: left;
    white-space: nowrap;
  }

  thead th {
    font-weight: 500;
    color: var(--p-text-muted-color);
    font-size: var(--font-size-xs);
  }

  tbody th {
    font-weight: 500;
  }

  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
}

.tt-meter {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 8rem;
}

.tt-meter-track {
  display: block;
  flex: 0 0 8rem;
  height: 0.5rem;
}

.tt-meter-bar {
  display: block;
  height: 100%;
  min-width: 2px;
  border-radius: 0 4px 4px 0;
  background: var(--p-blue-600);
}

.tt-meter-value {
  font-variant-numeric: tabular-nums;
}

.tt-muted {
  color: var(--p-text-muted-color);
}

.tt-bounds {
  margin: var(--space-2) 0 0;
  font-size: var(--font-size-sm);
}
</style>
