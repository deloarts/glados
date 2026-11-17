<script setup lang="ts">
// Utilization and availability per machine. The manual row without a
// machine has no capacity to divide by, so it is left out.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useChartTheme } from '@/shared/composables/useChartTheme'
import { useKpiFormat } from '../composables/useKpiFormat'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { UtilizationRowResult } from '../types/productionKpiResponse'

const props = defineProps<{
  rows: UtilizationRowResult[]
}>()

const { t } = useI18n()
const { formatPercent } = useKpiFormat()

const theme = useChartTheme({
  utilization: ['--p-primary-500', '#3b82f6'],
  availability: ['--p-orange-500', '#f97316'],
})

const machineRows = computed(() => props.rows.filter((row) => row.machine_id !== null))
const isEmpty = computed(() => machineRows.value.length === 0)

const chartData = computed(() => ({
  labels: machineRows.value.map((row) => row.machine_internal_name),
  datasets: [
    {
      label: t('productionKpi.charts.utilizationSeries'),
      data: machineRows.value.map((row) =>
        row.utilization.value === null ? null : row.utilization.value * 100,
      ),
      backgroundColor: theme.value.utilization,
      borderRadius: 4,
      maxBarThickness: 28,
    },
    {
      label: t('productionKpi.charts.availabilitySeries'),
      data: machineRows.value.map((row) =>
        row.availability?.value == null ? null : row.availability.value * 100,
      ),
      backgroundColor: theme.value.availability,
      borderRadius: 4,
      maxBarThickness: 28,
    },
  ],
}))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
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
  <div class="kpi-utilization-chart">
    <EmptyState
      v-if="isEmpty"
      :message="t('productionKpi.charts.utilizationEmpty')"
      icon="mdi mdi-chart-bar"
    />
    <Chart
      v-else
      type="bar"
      :data="chartData"
      :options="chartOptions"
      class="kpi-utilization-chart-canvas"
    />
  </div>
</template>

<style scoped lang="scss">
.kpi-utilization-chart {
  flex: 1;
  min-height: 14rem;
  width: 100%;
  position: relative;
  display: flex;
}

.kpi-utilization-chart-canvas {
  position: absolute;
  inset: 0;
  width: 100%;

  :deep(canvas) {
    width: 100%;
  }
}
</style>
