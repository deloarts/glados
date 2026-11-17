<script setup lang="ts">
// The year month by month: worked against target time as paired columns,
// and the balance at the end of each month as a separate line chart. Two
// charts on purpose, the balance has its own scale and must not share an
// axis with the monthly hours.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import EmptyState from '@/shared/components/EmptyState.vue'
import { formatDuration, formatSignedDuration } from '@/shared/utils/formatDuration'
import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { useTimeTrackingChartTheme } from '../composables/useTimeTrackingChartTheme'
import { monthName } from '@/core/utils/dates'
import type { TimeTrackingYearMonth } from '../types/timeTrackingTypes'

const props = defineProps<{
  months: TimeTrackingYearMonth[]
}>()

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()
const theme = useTimeTrackingChartTheme()

const HOUR = 3600

const labels = computed(() => props.months.map((month) => monthName(month.month)))

function hoursTick(value: string | number, signed = false): string {
  return `${formatNumber(Number(value), {
    maximumFractionDigits: 0,
    ...(signed ? { signDisplay: 'exceptZero' as const } : {}),
  })} h`
}

function axes(signed: boolean) {
  return {
    x: {
      grid: { display: false },
      border: { color: theme.value.grid },
      ticks: { color: theme.value.text, font: { size: 10 } },
    },
    y: {
      beginAtZero: !signed,
      grid: {
        color: (ctx: { tick?: { value: number } }) =>
          signed && ctx.tick?.value === 0 ? theme.value.text : theme.value.grid,
        drawTicks: false,
      },
      border: { display: false },
      ticks: {
        color: theme.value.text,
        font: { size: 10 },
        maxTicksLimit: 6,
        callback: (value: string | number) => hoursTick(value, signed),
      },
    },
  }
}

const hoursData = computed(() => ({
  labels: labels.value,
  datasets: [
    {
      label: t('timeTracking.stats.series.worked'),
      data: props.months.map((month) => month.worked_seconds / HOUR),
      backgroundColor: theme.value.worked,
      borderRadius: 4,
      maxBarThickness: 18,
    },
    {
      label: t('timeTracking.stats.series.target'),
      data: props.months.map((month) => month.target_seconds / HOUR),
      backgroundColor: theme.value.target,
      borderRadius: 4,
      maxBarThickness: 18,
    },
  ],
}))

const hoursOptions = computed(() => ({
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
        label: (item: { dataset: { label?: string }; parsed: { y: number | null } }) =>
          `${item.dataset.label}: ${formatDuration(Math.round((item.parsed.y ?? 0) * HOUR))}`,
      },
    },
  },
  scales: axes(false),
}))

const balanceMonths = computed(() => props.months.filter((m) => m.end_balance_seconds !== null))

const balanceData = computed(() => ({
  labels: balanceMonths.value.map((month) => monthName(month.month)),
  datasets: [
    {
      label: t('timeTracking.stats.yearBalance'),
      data: balanceMonths.value.map((month) => (month.end_balance_seconds ?? 0) / HOUR),
      borderColor: theme.value.worked,
      backgroundColor: theme.value.worked,
      borderWidth: 2,
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBorderColor: theme.value.surface,
      pointBorderWidth: 2,
      tension: 0,
    },
  ],
}))

const balanceOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index' as const, intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: {
      displayColors: false,
      callbacks: {
        label: (item: { parsed: { y: number | null } }) =>
          formatSignedDuration(Math.round((item.parsed.y ?? 0) * HOUR)),
      },
    },
  },
  scales: axes(true),
}))
</script>

<template>
  <div class="tt-year-charts" data-testid="time-tracking-year-chart">
    <EmptyState
      v-if="months.length === 0"
      :message="t('timeTracking.stats.noData')"
      icon="mdi mdi-chart-bar"
    />
    <template v-else>
      <div class="tt-year-chart">
        <div class="tt-chart-title">{{ t('timeTracking.stats.yearHours') }}</div>
        <div class="tt-chart">
          <Chart type="bar" :data="hoursData" :options="hoursOptions" class="tt-chart-canvas" />
        </div>
      </div>
      <div class="tt-year-chart">
        <div class="tt-chart-title">{{ t('timeTracking.stats.yearBalance') }}</div>
        <div class="tt-chart">
          <EmptyState
            v-if="balanceMonths.length === 0"
            :message="t('timeTracking.stats.noData')"
            icon="mdi mdi-chart-line"
          />
          <Chart v-else type="line" :data="balanceData" :options="balanceOptions" class="tt-chart-canvas" />
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.tt-year-charts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(22rem, 1fr));
  gap: var(--space-4);
}

.tt-year-chart {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.tt-chart-title {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--p-text-muted-color);
}

.tt-chart {
  height: 11rem;
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
