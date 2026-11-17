<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { CHART_BOX, CHART_PLOT, chartLayout } from '../utils/driveSizing/chart'
import type { ChartReference } from '../utils/driveSizing/chart'
import { useDriveSizingFormat } from '../utils/driveSizing/format'

const props = withDefaults(
  defineProps<{
    title: string
    description: string
    unit: string
    /** Polyline in data coordinates, time in s against the value. */
    points: ReadonlyArray<readonly [number, number]>
    duration: number
    references?: readonly ChartReference[]
  }>(),
  { references: () => [] },
)

const { t } = useI18n()
const fmt = useDriveSizingFormat()

const WIDTH = CHART_BOX.width
const HEIGHT = CHART_BOX.height
const LEFT = CHART_BOX.left
const TOP = CHART_BOX.top
const BOTTOM = CHART_BOX.bottom
const PLOT_WIDTH = CHART_PLOT.width
const PLOT_HEIGHT = CHART_PLOT.height

const scale = computed(() => chartLayout(props.points, props.duration, props.references))
const linePath = computed(() => scale.value.line)
const areaPath = computed(() => scale.value.area)
const labels = computed(() => scale.value.labels)
</script>

<template>
  <section class="ds-chart">
    <h3 class="ds-chart-title">{{ title }}</h3>
    <div class="ds-chart-card">
      <svg :viewBox="`0 0 ${WIDTH} ${HEIGHT}`" role="img" :aria-label="description" class="ds-chart-svg">
        <g>
          <template v-for="tick in scale.yTicks" :key="`y${tick}`">
            <line
              :x1="LEFT"
              :x2="LEFT + PLOT_WIDTH"
              :y1="scale.y(tick)"
              :y2="scale.y(tick)"
              class="ds-chart-grid"
            />
            <text :x="LEFT - 6" :y="scale.y(tick) + 4" text-anchor="end" class="ds-chart-text">
              {{ fmt.num(tick, 2) }}
            </text>
          </template>
          <template v-for="tick in scale.xTicks" :key="`x${tick}`">
            <line
              :x1="scale.x(tick)"
              :x2="scale.x(tick)"
              :y1="TOP"
              :y2="TOP + PLOT_HEIGHT"
              class="ds-chart-grid"
            />
            <text :x="scale.x(tick)" :y="HEIGHT - BOTTOM + 16" text-anchor="middle" class="ds-chart-text">
              {{ fmt.num(tick, 2) }}
            </text>
          </template>
        </g>

        <path :d="areaPath" class="ds-chart-area" />
        <line :x1="LEFT" :x2="LEFT + PLOT_WIDTH" :y1="scale.y(0)" :y2="scale.y(0)" class="ds-chart-zero" />

        <line
          v-for="reference in references"
          :key="`line${reference.tone}${reference.value}`"
          :x1="LEFT"
          :x2="LEFT + PLOT_WIDTH"
          :y1="scale.y(reference.value)"
          :y2="scale.y(reference.value)"
          :class="['ds-chart-ref', `ds-chart-ref--${reference.tone}`]"
        />
        <text
          v-for="{ reference, y } in labels"
          :key="`label${reference.tone}${reference.value}`"
          :x="LEFT + PLOT_WIDTH + 6"
          :y="y"
          :class="['ds-chart-label', `ds-chart-label--${reference.tone}`]"
        >
          <tspan>{{ reference.symbol[0] }}</tspan
          ><tspan v-if="reference.symbol[1]" dy="3" class="ds-chart-sub">{{ reference.symbol[1] }}</tspan>
        </text>

        <path :d="linePath" class="ds-chart-line" />

        <text :x="LEFT - 6" :y="TOP - 4" text-anchor="end" class="ds-chart-text ds-chart-unit">{{ unit }}</text>
        <text :x="LEFT + PLOT_WIDTH" :y="HEIGHT - 2" text-anchor="end" class="ds-chart-text ds-chart-unit">
          {{ t('tools.driveSizing.charts.time') }}
        </text>
      </svg>
    </div>
  </section>
</template>

<style scoped lang="scss">
.ds-chart {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
  break-inside: avoid;
}

.ds-chart-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.ds-chart-card {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.ds-chart-svg {
  display: block;
  width: 100%;
  height: auto;
}

.ds-chart-grid {
  stroke: var(--p-content-border-color);
  stroke-width: 1;
}

.ds-chart-zero {
  stroke: var(--p-text-color);
  stroke-width: 1.5;
}

.ds-chart-line {
  fill: none;
  stroke: var(--p-primary-color);
  stroke-width: 2;
  stroke-linejoin: round;
}

.ds-chart-area {
  fill: var(--p-primary-color);
  fill-opacity: 0.12;
}

.ds-chart-ref {
  stroke-width: 1.5;
  stroke-dasharray: 6 4;

  &--limit {
    stroke: var(--p-red-500);
  }

  &--rated {
    stroke: var(--p-orange-500);
  }

  &--mean {
    stroke: var(--p-text-muted-color);
    stroke-dasharray: 2 3;
  }
}

.ds-chart-text {
  font-size: var(--font-size-sm);
  fill: var(--p-text-muted-color);
  font-variant-numeric: tabular-nums;
}

.ds-chart-unit {
  font-weight: 600;
}

// The halo in the card colour keeps a label legible where it crosses a
// grid line.
.ds-chart-label {
  font-size: var(--font-size-sm);
  font-style: italic;
  font-weight: 600;
  paint-order: stroke;
  stroke: var(--p-content-background);
  stroke-width: 4px;
  stroke-linejoin: round;

  &--limit {
    fill: var(--p-red-500);
  }

  &--rated {
    fill: var(--p-orange-500);
  }

  &--mean {
    fill: var(--p-text-muted-color);
  }
}

.ds-chart-sub {
  font-size: var(--font-size-xs);
  font-style: normal;
}
</style>
