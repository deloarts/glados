<script setup lang="ts">
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

/**
 * A section through a plate with a hole for a screw: a plain clearance hole
 * (ISO 273), a counterbore (DIN 974) or a 90° countersink (ISO 15065, DIN 74).
 * Not to scale; the letters match the table columns.
 */
const props = defineProps<{
  variant: 'clearance' | 'counterbore' | 'countersink'
}>()

const { t } = useI18n()
const id = useId()

const TOP = 34
const BOTTOM = 140
const LEFT = 16
const RIGHT = 184
const CENTER = 100
const HOLE = 20 // half the through hole
const COUNTERBORE = 40 // half the counterbore diameter
const COUNTERBORE_DEPTH = 40
const COUNTERSINK = 46 // half the countersink diameter
const COUNTERSINK_DEPTH = COUNTERSINK - HOLE // 90°: the cone is as deep as it is wide on each side

const leftHalf = computed(() => {
  if (props.variant === 'counterbore') {
    return [
      [LEFT, TOP], [CENTER - COUNTERBORE, TOP], [CENTER - COUNTERBORE, TOP + COUNTERBORE_DEPTH],
      [CENTER - HOLE, TOP + COUNTERBORE_DEPTH], [CENTER - HOLE, BOTTOM], [LEFT, BOTTOM],
    ]
  }
  if (props.variant === 'countersink') {
    return [
      [LEFT, TOP], [CENTER - COUNTERSINK, TOP], [CENTER - HOLE, TOP + COUNTERSINK_DEPTH],
      [CENTER - HOLE, BOTTOM], [LEFT, BOTTOM],
    ]
  }
  return [[LEFT, TOP], [CENTER - HOLE, TOP], [CENTER - HOLE, BOTTOM], [LEFT, BOTTOM]]
})

const points = (list: number[][]) => list.map(([x, y]) => `${x},${y}`).join(' ')
const halves = computed(() => [
  points(leftHalf.value),
  points(leftHalf.value.map(([x, y]) => [2 * CENTER - (x as number), y as number])),
])

// The top dimension (counterbore or countersink diameter) and the depth on the
// right, if the variant has them; the through hole is always dimensioned below.
const top = computed(() => {
  if (props.variant === 'counterbore') return { half: COUNTERBORE, label: 'd1', depth: COUNTERBORE_DEPTH, depthLabel: 't' }
  if (props.variant === 'countersink') return { half: COUNTERSINK, label: 'd2', depth: COUNTERSINK_DEPTH, depthLabel: 't1' }
  return null
})
const holeLabel = computed(() => (props.variant === 'countersink' ? 'd1' : 'dh'))
</script>

<template>
  <figure class="hole-sketch">
    <svg viewBox="0 0 230 175" class="sketch" role="img" :aria-label="t(`tools.threads.sketches.${variant}Aria`)">
      <defs>
        <pattern :id="`${id}-hatch`" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" class="sketch-hatch" />
        </pattern>
        <marker :id="`${id}-arrow`" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" class="sketch-arrowhead" />
        </marker>
      </defs>
      <polygon v-for="(half, index) in halves" :key="index" :points="half" :fill="`url(#${id}-hatch)`" class="sketch-plate" />
      <line :x1="CENTER" :x2="CENTER" :y1="TOP - 24" :y2="BOTTOM + 10" class="sketch-axis" />

      <template v-if="top">
        <line :x1="CENTER - top.half" :x2="CENTER + top.half" y1="18" y2="18" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sketch-dimension" />
        <text :x="CENTER + top.half + 6" y="22" class="sketch-label">{{ top.label }}</text>
        <line :x1="RIGHT" :x2="RIGHT + 30" :y1="TOP" :y2="TOP" class="sketch-extension" />
        <line :x1="CENTER + HOLE" :x2="RIGHT + 30" :y1="TOP + top.depth" :y2="TOP + top.depth" class="sketch-extension" />
        <line :x1="RIGHT + 22" :x2="RIGHT + 22" :y1="TOP" :y2="TOP + top.depth" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sketch-dimension" />
        <text :x="RIGHT + 27" :y="TOP + top.depth / 2 + 4" class="sketch-label">{{ top.depthLabel }}</text>
      </template>
      <text v-if="variant === 'countersink'" :x="CENTER" :y="TOP + COUNTERSINK_DEPTH - 6" text-anchor="middle" class="sketch-label">90°</text>

      <line :x1="CENTER - HOLE" :x2="CENTER + HOLE" :y1="BOTTOM + 16" :y2="BOTTOM + 16" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sketch-dimension" />
      <line :x1="CENTER - HOLE" :x2="CENTER - HOLE" :y1="BOTTOM" :y2="BOTTOM + 22" class="sketch-extension" />
      <line :x1="CENTER + HOLE" :x2="CENTER + HOLE" :y1="BOTTOM" :y2="BOTTOM + 22" class="sketch-extension" />
      <text :x="CENTER + HOLE + 6" :y="BOTTOM + 20" class="sketch-label">{{ holeLabel }}</text>
    </svg>
    <figcaption>{{ t(`tools.threads.sketches.${variant}`) }}</figcaption>
  </figure>
</template>

<style scoped lang="scss">
.hole-sketch {
  margin: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);

  figcaption {
    font-size: var(--font-size-xs);
    color: var(--p-text-muted-color);
    text-align: center;
  }
}

.sketch {
  display: block;
  width: 100%;
  max-width: 260px;
  height: auto;
}

.sketch-hatch {
  stroke: var(--p-text-muted-color);
  stroke-width: 1;
}

.sketch-plate {
  stroke: var(--p-text-color);
  stroke-width: 1.25;
}

.sketch-axis {
  stroke: var(--p-text-muted-color);
  stroke-width: 1;
  stroke-dasharray: 12 3 2 3;
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

.sketch-label {
  font-size: var(--font-size-sm);
  fill: var(--p-text-color);
}
</style>
