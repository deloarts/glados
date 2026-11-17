<script setup lang="ts">
// Weekly schedule adherence and on-time delivery, one line each, with theme
// colours resolved from CSS variables.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useChartTheme } from '@/shared/composables/useChartTheme'
import { useKpiFormat } from '../composables/useKpiFormat'
import { formatIsoWeekLabel } from '../utils/isoWeekLabel'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { WeeklyKpiPointResult } from '../types/productionKpiResponse'

const props = defineProps<{
  points: WeeklyKpiPointResult[]
}>()

const { t } = useI18n()
const { formatPercent } = useKpiFormat()

// Fixed series colours, primary and orange, far enough apart for
// colour-blind readers.
const theme = useChartTheme({
  adherence: ['--p-primary-500', '#3b82f6'],
  onTime: ['--p-orange-500', '#f97316'],
})

// An explicit empty state instead of flat lines that look like real zeros.
const isEmpty = computed(
  () =>
    props.points.length === 0 ||
    props.points.every((p) => p.schedule_adherence.value === null && p.on_time_delivery.value === null),
)

const chartData = computed(() => ({
  labels: props.points.map((p) => formatIsoWeekLabel(p.iso_week, t('productionKpi.weekPrefix'))),
  datasets: [
    {
      label: t('productionKpi.charts.scheduleAdherenceSeries'),
      data: props.points.map((p) =>
        p.schedule_adherence.value === null ? null : p.schedule_adherence.value * 100,
      ),
      borderColor: theme.value.adherence,
      backgroundColor: theme.value.adherence,
      borderWidth: 2,
      pointRadius: 3,
      pointHoverRadius: 5,
      tension: 0.2,
      spanGaps: false,
    },
    {
      label: t('productionKpi.charts.onTimeDeliverySeries'),
      data: props.points.map((p) =>
        p.on_time_delivery.value === null ? null : p.on_time_delivery.value * 100,
      ),
      borderColor: theme.value.onTime,
      backgroundColor: theme.value.onTime,
      borderWidth: 2,
      pointRadius: 3,
      pointHoverRadius: 5,
      tension: 0.2,
      spanGaps: false,
    },
  ],
}))

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
        label: (item: { dataset: { label?: string }; parsed: { y: number | null } }) =>
          item.parsed.y === null
            ? `${item.dataset.label}: ${t('productionKpi.tiles.naValue')}`
            : `${item.dataset.label}: ${formatPercent(item.parsed.y / 100)}`,
      },
    },
  },
  scales: {
    x: {
      grid: { display: false },
      border: { color: theme.value.grid },
      ticks: { color: theme.value.text, font: { size: 10 } },
    },
    y: {
      min: 0,
      max: 100,
      grid: { color: theme.value.grid, drawTicks: false },
      border: { display: false },
      ticks: {
        color: theme.value.text,
        font: { size: 10 },
        callback: (value: string | number) => `${value}%`,
      },
    },
  },
}))
</script>

<template>
  <div class="kpi-weekly-chart">
    <EmptyState
      v-if="isEmpty"
      class="kpi-weekly-chart-empty"
      :message="t('productionKpi.charts.weeklyEmpty')"
      icon="mdi mdi-chart-line"
    />
    <Chart v-else type="line" :data="chartData" :options="chartOptions" class="kpi-weekly-chart-canvas" />
  </div>
</template>

<style scoped lang="scss">
.kpi-weekly-chart {
  flex: 1;
  min-height: 14rem;
  width: 100%;
  position: relative;
  display: flex;
}

// flex: 1 so the empty state spans the card width like the tables' do.
.kpi-weekly-chart-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.kpi-weekly-chart-canvas {
  position: absolute;
  inset: 0;
  width: 100%;

  :deep(canvas) {
    width: 100%;
  }
}
</style>
