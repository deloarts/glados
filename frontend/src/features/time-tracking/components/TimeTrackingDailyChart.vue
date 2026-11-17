<script setup lang="ts">
// Worked time per day against the day's target, as stacked columns: the
// part up to the target, the part above it, and the part still missing to
// it, so every column's top reads as either the target or the overshoot.
// Days after today and days without target or work are left out of the
// axis. Values are hours on the axis and h:mm in the tooltip.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import EmptyState from '@/shared/components/EmptyState.vue'
import { dayLabel } from '../utils/timeTrackingMonth'
import { formatDuration } from '@/shared/utils/formatDuration'
import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { useTimeTrackingChartTheme } from '../composables/useTimeTrackingChartTheme'
import type { TimeTrackingDay } from '../types/timeTrackingTypes'

const props = defineProps<{
  days: TimeTrackingDay[]
  todayDate: string | null
}>()

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()
const theme = useTimeTrackingChartTheme()

const HOUR = 3600

const plotted = computed(() =>
  props.days.filter(
    (day) =>
      (props.todayDate === null || day.date <= props.todayDate) &&
      ((day.worked_seconds ?? 0) > 0 || day.target_seconds > 0),
  ),
)

function parts(day: TimeTrackingDay) {
  const worked = day.worked_seconds ?? 0
  return {
    within: Math.min(worked, day.target_seconds),
    over: Math.max(worked - day.target_seconds, 0),
    short: Math.max(day.target_seconds - worked, 0),
  }
}

const chartData = computed(() => {
  const rows = plotted.value.map(parts)
  const dataset = (label: string, color: string, values: number[]) => ({
    label,
    data: values.map((seconds) => seconds / HOUR),
    backgroundColor: color,
    borderColor: theme.value.surface,
    // A surface-coloured edge on top keeps stacked segments apart.
    borderWidth: { top: 2, bottom: 0, left: 0, right: 0 },
    borderRadius: 2,
    maxBarThickness: 24,
    stack: 'day',
  })
  return {
    labels: plotted.value.map((day) => dayLabel(day.date)),
    datasets: [
      dataset(t('timeTracking.stats.series.worked'), theme.value.worked, rows.map((r) => r.within)),
      dataset(t('timeTracking.stats.series.over'), theme.value.over, rows.map((r) => r.over)),
      dataset(t('timeTracking.stats.series.short'), theme.value.short, rows.map((r) => r.short)),
    ],
  }
})

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index' as const, intersect: false },
  plugins: {
    legend: {
      display: true,
      labels: { color: theme.value.text, usePointStyle: true, boxHeight: 6 },
    },
    tooltip: {
      callbacks: {
        title: (items: { dataIndex: number }[]) => {
          const day = plotted.value[items[0]?.dataIndex ?? -1]
          return day ? dayLabel(day.date) : ''
        },
        label: (item: { dataset: { label?: string }; parsed: { y: number | null } }) =>
          `${item.dataset.label}: ${formatDuration(Math.round((item.parsed.y ?? 0) * HOUR))}`,
      },
    },
  },
  scales: {
    x: {
      stacked: true,
      grid: { display: false },
      border: { color: theme.value.grid },
      ticks: {
        color: theme.value.text,
        font: { size: 10 },
        maxRotation: 0,
        autoSkip: true,
        autoSkipPadding: 16,
      },
    },
    y: {
      stacked: true,
      beginAtZero: true,
      grid: { color: theme.value.grid, drawTicks: false },
      border: { display: false },
      ticks: {
        color: theme.value.text,
        font: { size: 10 },
        maxTicksLimit: 6,
        callback: (value: string | number) =>
          `${formatNumber(Number(value), { maximumFractionDigits: 1 })} h`,
      },
    },
  },
}))
</script>

<template>
  <div class="tt-chart" data-testid="time-tracking-daily-chart">
    <EmptyState
      v-if="plotted.length === 0"
      :message="t('timeTracking.stats.noData')"
      icon="mdi mdi-chart-bar"
    />
    <Chart v-else type="bar" :data="chartData" :options="chartOptions" class="tt-chart-canvas" />
  </div>
</template>

<style scoped lang="scss">
.tt-chart {
  height: 11rem;
  width: 100%;
  position: relative;
  display: flex;
}

.tt-chart-canvas {
  position: absolute;
  inset: 0;
  width: 100%;

  :deep(canvas) {
    width: 100%;
  }
}
</style>
