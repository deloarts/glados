<script setup lang="ts">
// The running balance over the month, one point per day the time tracking
// system reported a balance for, up to today. A single series, so no
// legend; the zero line is drawn stronger than the rest of the grid so the
// sign of the balance reads at a glance.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import EmptyState from '@/shared/components/EmptyState.vue'
import { dayLabel } from '../utils/timeTrackingMonth'
import { formatSignedDuration } from '@/shared/utils/formatDuration'
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

const points = computed(() =>
  props.days.filter(
    (day) =>
      day.running_balance_seconds !== null &&
      (props.todayDate === null || day.date <= props.todayDate),
  ),
)

const chartData = computed(() => ({
  labels: points.value.map((day) => dayLabel(day.date)),
  datasets: [
    {
      label: t('timeTracking.stats.balanceTitle'),
      data: points.value.map((day) => (day.running_balance_seconds ?? 0) / HOUR),
      borderColor: theme.value.worked,
      backgroundColor: `${theme.value.worked}1a`,
      borderWidth: 2,
      fill: 'origin',
      cubicInterpolationMode: 'monotone' as const,
      pointRadius: 0,
      pointHoverRadius: 5,
      pointBackgroundColor: theme.value.worked,
      pointHoverBorderColor: theme.value.surface,
      pointHoverBorderWidth: 2,
    },
  ],
}))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index' as const, intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: {
      displayColors: false,
      callbacks: {
        title: (items: { dataIndex: number }[]) => {
          const day = points.value[items[0]?.dataIndex ?? -1]
          return day ? dayLabel(day.date) : ''
        },
        label: (item: { parsed: { y: number | null } }) =>
          formatSignedDuration(Math.round((item.parsed.y ?? 0) * HOUR)),
      },
    },
  },
  scales: {
    x: {
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
      grid: {
        color: (ctx: { tick?: { value: number } }) =>
          ctx.tick?.value === 0 ? theme.value.text : theme.value.grid,
        drawTicks: false,
      },
      border: { display: false },
      ticks: {
        color: theme.value.text,
        font: { size: 10 },
        maxTicksLimit: 6,
        callback: (value: string | number) =>
          `${formatNumber(Number(value), { maximumFractionDigits: 1, signDisplay: 'exceptZero' })} h`,
      },
    },
  },
}))
</script>

<template>
  <div class="tt-chart" data-testid="time-tracking-balance-chart">
    <EmptyState
      v-if="points.length === 0"
      :message="t('timeTracking.stats.noData')"
      icon="mdi mdi-chart-line"
    />
    <Chart v-else type="line" :data="chartData" :options="chartOptions" class="tt-chart-canvas" />
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
