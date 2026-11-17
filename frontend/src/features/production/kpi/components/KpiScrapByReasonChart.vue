<script setup lang="ts">
// Scrapped quantity per reason as horizontal bars, sorted descending. One
// series, so no legend.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useChartTheme } from '@/shared/composables/useChartTheme'
import { useKpiFormat } from '../composables/useKpiFormat'
import EmptyState from '@/shared/components/EmptyState.vue'
import { scrapReasonLabelKey } from '@/shared/utils/scrapReasons'

import type { ScrapReason } from '@/shared/utils/scrapReasons'
import type { ScrapByReasonRowResult } from '../types/productionKpiResponse'

const props = defineProps<{
  rows: ScrapByReasonRowResult[]
}>()

const { t } = useI18n()
const { formatPercent, formatQuantity } = useKpiFormat()

const theme = useChartTheme({
  bar: ['--p-red-500', '#ef4444'],
})

// Unknown reasons fall back to the raw string.
function reasonLabel(reason: string): string {
  const key = scrapReasonLabelKey(reason as ScrapReason)
  const translated = t(key)
  return translated === key ? reason : translated
}

function formatShare(value: number | null): string {
  return value === null ? t('productionKpi.tiles.naValue') : formatPercent(value)
}

const isEmpty = computed(() => props.rows.length === 0)

const chartData = computed(() => ({
  labels: props.rows.map((row) => reasonLabel(row.reason)),
  datasets: [
    {
      label: t('productionKpi.charts.scrapByReasonSeries'),
      data: props.rows.map((row) => row.quantity),
      backgroundColor: theme.value.bar,
      borderRadius: 4,
      maxBarThickness: 22,
    },
  ],
}))

const chartOptions = computed(() => ({
  indexAxis: 'y' as const,
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (item: { dataIndex: number; parsed: { x: number | null } }) => {
          const row = props.rows[item.dataIndex]
          const share = row ? formatShare(row.share.value) : ''
          return `${formatQuantity(item.parsed.x ?? 0)} (${share})`
        },
      },
    },
  },
  scales: {
    x: {
      min: 0,
      grid: { color: theme.value.grid, drawTicks: false },
      border: { display: false },
      ticks: { color: theme.value.text, font: { size: 10 } },
    },
    y: {
      grid: { display: false },
      border: { color: theme.value.grid },
      ticks: { color: theme.value.text, font: { size: 10 } },
    },
  },
}))
</script>

<template>
  <div class="kpi-scrap-chart">
    <EmptyState
      v-if="isEmpty"
      :message="t('productionKpi.charts.scrapByReasonEmpty')"
      icon="mdi mdi-chart-bar"
    />
    <Chart
      v-else
      type="bar"
      :data="chartData"
      :options="chartOptions"
      class="kpi-scrap-chart-canvas"
    />
  </div>
</template>

<style scoped lang="scss">
.kpi-scrap-chart {
  flex: 1;
  min-height: 14rem;
  width: 100%;
  position: relative;
  display: flex;
}

.kpi-scrap-chart-canvas {
  position: absolute;
  inset: 0;
  width: 100%;

  :deep(canvas) {
    width: 100%;
  }
}
</style>
