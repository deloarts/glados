<script setup lang="ts">
import { computed } from 'vue'

import { useChartTheme } from '@/shared/composables/useChartTheme'
import { localeTag } from '@/core/utils/dates'
import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'

const props = defineProps<{
  points: { day: number; cumulative: number; date: Date }[]
  // Values in the caller's unit, cents here.
  formatValue?: (value: number) => string
}>()

const { formatNumber } = useLocaleFormat()

// Resolved here, since a withDefaults default is hoisted out of setup and
// cannot reach formatNumber.
function resolveFormatValue(value: number): string {
  if (props.formatValue) return props.formatValue(value)
  return formatNumber(Math.round(value), { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

const theme = useChartTheme({
  line: ['--p-primary-500', '#3b82f6'],
  fillFrom: ['--p-primary-400', '#60a5fa'],
  surface: ['--p-surface-0', '#ffffff'],
})

const chartData = computed(() => ({
  labels: props.points.map((p) =>
    p.date.toLocaleDateString(localeTag(), { day: 'numeric', month: 'short' }),
  ),
  datasets: [
    {
      data: props.points.map((p) => p.cumulative),
      borderColor: theme.value.line,
      borderWidth: 2,
      // Cumulative spend only ever steps up, so a light fill under the line
      // reads as "committed so far" without implying values between points.
      fill: true,
      backgroundColor: (ctx: {
        chart: { ctx: CanvasRenderingContext2D; chartArea?: { top: number; bottom: number } }
      }) => {
        const { ctx: canvas, chartArea } = ctx.chart
        if (!chartArea) return 'transparent'
        const gradient = canvas.createLinearGradient(0, chartArea.top, 0, chartArea.bottom)
        gradient.addColorStop(0, `${theme.value.fillFrom}59`)
        gradient.addColorStop(1, `${theme.value.fillFrom}00`)
        return gradient
      },
      // Monotone, since plain tension overshoots and draws dips that are not in
      // the data.
      cubicInterpolationMode: 'monotone' as const,
      pointRadius: 0,
      pointHoverRadius: 5,
      pointBackgroundColor: theme.value.line,
      pointHoverBorderColor: theme.value.surface,
      pointHoverBorderWidth: 2,
    },
  ],
}))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  // Hovering anywhere on a column finds the nearest point.
  interaction: { mode: 'index' as const, intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: {
      displayColors: false,
      callbacks: {
        label: (item: { parsed: { y: number | null } }) => resolveFormatValue(item.parsed.y ?? 0),
      },
    },
  },
  scales: {
    x: {
      grid: { display: false },
      border: { color: theme.value.grid },
      ticks: {
        color: theme.value.text,
        maxRotation: 0,
        autoSkip: true,
        maxTicksLimit: 8,
        font: { size: 10 },
      },
    },
    y: {
      beginAtZero: true,
      grid: { color: theme.value.grid, drawTicks: false },
      border: { display: false },
      ticks: {
        color: theme.value.text,
        maxTicksLimit: 5,
        font: { size: 10 },
        callback: (value: string | number) => resolveFormatValue(Number(value)),
      },
    },
  },
}))
</script>

<template>
  <div class="spend-chart">
    <Chart type="line" :data="chartData" :options="chartOptions" class="spend-chart-canvas" />
  </div>
</template>

<style scoped lang="scss">
.spend-chart {
  flex: 1 1 auto;
  min-height: 0;
  position: relative;
}

.spend-chart-canvas {
  position: absolute;
  inset: 0;
}
</style>
