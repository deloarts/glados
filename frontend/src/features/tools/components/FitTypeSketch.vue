<script setup lang="ts">
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import type { FitType } from '../utils/iso286/fit'

const props = defineProps<{
  type: FitType
}>()

const { t } = useI18n()
const id = useId()

// A schematic section through a hole wall (hatched, top) and a shaft (bottom).
// Each part's edge lies inside its tolerance zone; up means larger. The
// numbered arrows match the two figures of the fit type, in the order
// `fitFigures` returns them.
const HOLE_X = 30
const HOLE_RIGHT = 190
const SHAFT_X = 60
const SHAFT_RIGHT = 160
const BOTTOM = 182

interface Layout {
  holeTop: number
  holeBottom: number
  shaftTop: number
  shaftBottom: number
  arrows: [from: number, to: number][]
}

const LAYOUTS: Record<FitType, Layout> = {
  clearance: { holeTop: 50, holeBottom: 70, shaftTop: 95, shaftBottom: 115, arrows: [[50, 115], [70, 95]] },
  transition: { holeTop: 60, holeBottom: 90, shaftTop: 45, shaftBottom: 75, arrows: [[60, 75], [45, 90]] },
  interference: { holeTop: 80, holeBottom: 100, shaftTop: 45, shaftBottom: 65, arrows: [[45, 100], [65, 80]] },
}

const layout = computed(() => LAYOUTS[props.type])

const arrows = computed(() =>
  layout.value.arrows.map(([from, to], index) => ({
    x: 212 + index * 34,
    from,
    to,
    number: index + 1,
  })),
)

// Every edge an arrow ends on gets a dashed extension line out to the arrows,
// starting from whichever part the edge belongs to.
const extensions = computed(() => {
  const l = layout.value
  const holeEdges = new Set([l.holeTop, l.holeBottom])
  const ends = new Set(l.arrows.flat())
  return [...ends].map((y) => ({ y, from: holeEdges.has(y) ? HOLE_RIGHT : SHAFT_RIGHT }))
})
</script>

<template>
  <svg
    viewBox="0 0 280 190"
    class="sketch"
    role="img"
    :aria-label="t(`tools.fitCalculator.explain.fitSketchAria.${type}`)"
  >
    <defs>
      <pattern :id="`${id}-hatch`" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="6" class="sketch-hatch" />
      </pattern>
      <marker :id="`${id}-arrow`" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" class="sketch-arrowhead" />
      </marker>
    </defs>

    <rect :x="HOLE_X" y="12" :width="HOLE_RIGHT - HOLE_X" :height="layout.holeTop - 12" :fill="`url(#${id}-hatch)`" class="sketch-material" />
    <rect :x="HOLE_X" :y="layout.holeTop" :width="HOLE_RIGHT - HOLE_X" :height="layout.holeBottom - layout.holeTop" class="sketch-zone sketch-zone--hole" />

    <rect :x="SHAFT_X" :y="layout.shaftBottom" :width="SHAFT_RIGHT - SHAFT_X" :height="BOTTOM - layout.shaftBottom" class="sketch-body" />
    <rect :x="SHAFT_X" :y="layout.shaftTop" :width="SHAFT_RIGHT - SHAFT_X" :height="layout.shaftBottom - layout.shaftTop" class="sketch-zone sketch-zone--shaft" />

    <line v-for="ext in extensions" :key="ext.y" :x1="ext.from" x2="262" :y1="ext.y" :y2="ext.y" class="sketch-extension" />

    <g v-for="arrow in arrows" :key="arrow.number">
      <line
        :x1="arrow.x"
        :x2="arrow.x"
        :y1="arrow.from"
        :y2="arrow.to"
        :marker-start="`url(#${id}-arrow)`"
        :marker-end="`url(#${id}-arrow)`"
        class="sketch-dimension"
      />
      <circle :cx="arrow.x + 13" :cy="(arrow.from + arrow.to) / 2" r="7.5" class="sketch-badge" />
      <text :x="arrow.x + 13" :y="(arrow.from + arrow.to) / 2 + 3.5" text-anchor="middle" class="sketch-badge-text">
        {{ arrow.number }}
      </text>
    </g>
  </svg>
</template>

<style scoped lang="scss">
.sketch {
  display: block;
  width: 100%;
  max-width: 280px;
  height: auto;
}

.sketch-hatch {
  stroke: var(--p-text-muted-color);
  stroke-width: 1;
}

.sketch-material {
  stroke: var(--p-text-muted-color);
  stroke-width: 1;
}

.sketch-body {
  fill: var(--p-orange-500);
  fill-opacity: 0.25;
  stroke: var(--p-orange-500);
  stroke-width: 1;
}

.sketch-zone {
  stroke-width: 1.5;

  &--hole {
    fill: var(--p-blue-500);
    fill-opacity: 0.45;
    stroke: var(--p-blue-500);
  }

  // Drawn over the hole so an overlap (transition, interference) stays visible.
  &--shaft {
    fill: var(--p-orange-500);
    fill-opacity: 0.6;
    stroke: var(--p-orange-500);
  }
}

.sketch-extension {
  stroke: var(--p-text-muted-color);
  stroke-width: 0.75;
  stroke-dasharray: 3 3;
}

.sketch-dimension {
  stroke: var(--p-text-color);
  stroke-width: 1;
}

.sketch-arrowhead {
  fill: var(--p-text-color);
}

.sketch-badge {
  fill: var(--p-text-color);
}

.sketch-badge-text {
  font-size: var(--font-size-xs);
  font-weight: 600;
  fill: var(--p-content-background);
}
</style>
