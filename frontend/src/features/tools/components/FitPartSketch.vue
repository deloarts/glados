<script setup lang="ts">
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import type { FitPart } from '../utils/iso286/toleranceClass'

const props = defineProps<{
  part: FitPart
}>()

const { t } = useI18n()
const id = useId()

// A schematic, not to scale: the part's edge lies somewhere inside its
// tolerance zone; sizes are measured from the datum at the bottom, the
// deviations from the zero line, which marks the nominal size. The hole's zone
// is drawn above the zero line, the shaft's below it, as for most fits.
const DATUM = 190
const PART_X = 110
const PART_WIDTH = 90

interface Arrow {
  x: number
  from: number
  to: number
  label: string
  side: 'left' | 'right'
}

const geometry = computed(() => {
  const isHole = props.part === 'hole'
  const zero = isHole ? 110 : 55
  const zoneTop = isHole ? 65 : 75
  const zoneBottom = isHole ? 90 : 100
  const upper = isHole ? 'ES' : 'es'
  const lower = isHole ? 'EI' : 'ei'
  const arrows: Arrow[] = [
    { x: 40, from: DATUM, to: zero, label: 'N', side: 'left' },
    { x: 62, from: DATUM, to: zoneBottom, label: t('tools.fitCalculator.minSize'), side: 'left' },
    { x: 84, from: DATUM, to: zoneTop, label: t('tools.fitCalculator.maxSize'), side: 'left' },
    {
      x: 218,
      from: zero,
      to: isHole ? zoneBottom : zoneTop,
      label: isHole ? lower : upper,
      side: 'right',
    },
    {
      x: 242,
      from: zero,
      to: isHole ? zoneTop : zoneBottom,
      label: isHole ? upper : lower,
      side: 'right',
    },
    { x: 266, from: zoneBottom, to: zoneTop, label: 'T', side: 'right' },
  ]
  return { isHole, zero, zoneTop, zoneBottom, arrows }
})

function labelTransform(arrow: Arrow): string {
  const mid = (arrow.from + arrow.to) / 2
  return arrow.side === 'left' ? `rotate(-90 ${arrow.x - 5} ${mid})` : ''
}
</script>

<template>
  <svg
    viewBox="0 0 300 200"
    class="sketch"
    role="img"
    :aria-label="t(`tools.fitCalculator.explain.${part}SketchAria`)"
  >
    <defs>
      <pattern :id="`${id}-hatch`" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="6" class="sketch-hatch" />
      </pattern>
      <marker :id="`${id}-arrow`" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" class="sketch-arrowhead" />
      </marker>
    </defs>

    <!-- Extension lines from the zone edges and the datum out to the arrows. -->
    <line x1="30" x2="290" :y1="geometry.zoneTop" :y2="geometry.zoneTop" class="sketch-extension" />
    <line x1="30" x2="290" :y1="geometry.zoneBottom" :y2="geometry.zoneBottom" class="sketch-extension" />
    <line x1="30" x2="210" :y1="DATUM" :y2="DATUM" class="sketch-datum" />

    <template v-if="geometry.isHole">
      <rect :x="PART_X" y="20" :width="PART_WIDTH" :height="geometry.zoneTop - 20" :fill="`url(#${id}-hatch)`" class="sketch-material" />
      <rect :x="PART_X" :y="geometry.zoneBottom" :width="PART_WIDTH" :height="DATUM - geometry.zoneBottom" class="sketch-body sketch-body--hole" />
      <rect :x="PART_X" :y="geometry.zoneTop" :width="PART_WIDTH" :height="geometry.zoneBottom - geometry.zoneTop" class="sketch-zone sketch-zone--hole" />
    </template>
    <template v-else>
      <rect :x="PART_X" :y="geometry.zoneBottom" :width="PART_WIDTH" :height="DATUM - geometry.zoneBottom" class="sketch-body sketch-body--shaft" />
      <rect :x="PART_X" :y="geometry.zoneTop" :width="PART_WIDTH" :height="geometry.zoneBottom - geometry.zoneTop" class="sketch-zone sketch-zone--shaft" />
    </template>

    <line x1="30" x2="290" :y1="geometry.zero" :y2="geometry.zero" class="sketch-zero" />

    <g v-for="arrow in geometry.arrows" :key="`${arrow.x}`">
      <line
        :x1="arrow.x"
        :x2="arrow.x"
        :y1="arrow.from"
        :y2="arrow.to"
        :marker-start="arrow.side === 'right' ? `url(#${id}-arrow)` : undefined"
        :marker-end="`url(#${id}-arrow)`"
        class="sketch-dimension"
      />
      <text
        :x="arrow.side === 'left' ? arrow.x - 5 : arrow.x + 4"
        :y="arrow.side === 'left' ? (arrow.from + arrow.to) / 2 : (arrow.from + arrow.to) / 2 + 4"
        :transform="labelTransform(arrow)"
        :text-anchor="arrow.side === 'left' ? 'middle' : 'start'"
        class="sketch-label"
      >
        {{ arrow.label }}
      </text>
    </g>
  </svg>
</template>

<style scoped lang="scss">
.sketch {
  display: block;
  width: 100%;
  max-width: 300px;
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
  &--hole {
    fill: var(--p-blue-500);
    fill-opacity: 0.08;
  }

  &--shaft {
    fill: var(--p-orange-500);
    fill-opacity: 0.25;
    stroke: var(--p-orange-500);
    stroke-width: 1;
  }
}

.sketch-zone {
  stroke-width: 1.5;

  &--hole {
    fill: var(--p-blue-500);
    fill-opacity: 0.45;
    stroke: var(--p-blue-500);
  }

  &--shaft {
    fill: var(--p-orange-500);
    fill-opacity: 0.6;
    stroke: var(--p-orange-500);
  }
}

.sketch-zero {
  stroke: var(--p-text-color);
  stroke-width: 1.25;
}

.sketch-extension,
.sketch-datum {
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
  font-size: var(--font-size-xs);
  fill: var(--p-text-color);
}
</style>
