<script setup lang="ts">
// Four headline numbers for the month: days worked, the average day, the
// longest day and how many days ended above their target. A number is the
// whole message here, so these are tiles rather than charts.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODate } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { formatDuration } from '@/shared/utils/formatDuration'
import { monthKpis } from '../utils/timeTrackingStats'
import type { TimeTrackingDay } from '../types/timeTrackingTypes'

const props = defineProps<{
  /** Only the days the statistics count, see countedDays(). */
  days: TimeTrackingDay[]
}>()

const { t } = useI18n()

const kpis = computed(() => monthKpis(props.days))

const tiles = computed(() => [
  {
    key: 'daysWorked',
    icon: 'mdi mdi-calendar-check-outline',
    label: t('timeTracking.stats.kpi.daysWorked'),
    value: String(kpis.value.daysWorked),
    note: null as string | null,
  },
  {
    key: 'averageDay',
    icon: 'mdi mdi-timer-outline',
    label: t('timeTracking.stats.kpi.averageDay'),
    value:
      kpis.value.averageDaySeconds === null
        ? getEmptyPlaceholder()
        : formatDuration(Math.round(kpis.value.averageDaySeconds)),
    note: null,
  },
  {
    key: 'longestDay',
    icon: 'mdi mdi-arrow-expand-vertical',
    label: t('timeTracking.stats.kpi.longestDay'),
    value: kpis.value.longestDay
      ? formatDuration(kpis.value.longestDay.seconds)
      : getEmptyPlaceholder(),
    note: kpis.value.longestDay ? formatISODate(kpis.value.longestDay.date) : null,
  },
  {
    key: 'overtimeDays',
    icon: 'mdi mdi-trending-up',
    label: t('timeTracking.stats.kpi.overtimeDays'),
    value: String(kpis.value.overtimeDays),
    note: null,
  },
])
</script>

<template>
  <section class="tt-kpis" data-testid="time-tracking-kpis">
    <div v-for="tile in tiles" :key="tile.key" class="card tt-kpi" :data-testid="`time-tracking-kpi-${tile.key}`">
      <span class="tt-kpi-label">
        <i :class="tile.icon" aria-hidden="true" />
        {{ tile.label }}
      </span>
      <span class="tt-kpi-value">{{ tile.value }}</span>
      <span v-if="tile.note" class="tt-kpi-note">{{ tile.note }}</span>
    </div>
  </section>
</template>

<style scoped lang="scss">
.tt-kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: var(--space-1);
}

.tt-kpi {
  padding: var(--space-3) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  height: auto;
}

.tt-kpi-label {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.tt-kpi-value {
  font-size: var(--font-size-xl);
  font-weight: 600;
}

.tt-kpi-note {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
