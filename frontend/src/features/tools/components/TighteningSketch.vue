<script setup lang="ts">
import { useId } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const id = useId()

// A bolted joint: two clamped plates, a hexagon bolt and a nut. Turning the
// head with the torque MA stretches the bolt, and the preload force FV clamps
// the plates together. Not to scale.
const CENTER = 130
const PLATE_LEFT = 40
const PLATE_RIGHT = 220
const PLATE_TOP = 78
const PLATE_JOINT = 108
const PLATE_BOTTOM = 138
const SHANK = 13 // half the shank width
const HOLE = 16 // half the clearance hole
const HEAD = 34 // half the head width
const HEAD_TOP = 56
const NUT_BOTTOM = 160

const plate = (top: number, bottom: number, side: 'left' | 'right') => {
  const [outer, inner] = side === 'left' ? [PLATE_LEFT, CENTER - HOLE] : [CENTER + HOLE, PLATE_RIGHT]
  return `${outer},${top} ${inner},${top} ${inner},${bottom} ${outer},${bottom}`
}
</script>

<template>
  <svg viewBox="0 0 260 190" class="sketch" role="img" :aria-label="t('tools.threads.sketches.tighteningAria')">
    <defs>
      <pattern :id="`${id}-hatch-a`" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="6" class="sketch-hatch" />
      </pattern>
      <pattern :id="`${id}-hatch-b`" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(-45)">
        <line x1="0" y1="0" x2="0" y2="6" class="sketch-hatch" />
      </pattern>
      <marker :id="`${id}-arrow`" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" class="sketch-arrowhead" />
      </marker>
    </defs>

    <polygon :points="plate(PLATE_TOP, PLATE_JOINT, 'left')" :fill="`url(#${id}-hatch-a)`" class="sketch-plate" />
    <polygon :points="plate(PLATE_TOP, PLATE_JOINT, 'right')" :fill="`url(#${id}-hatch-a)`" class="sketch-plate" />
    <polygon :points="plate(PLATE_JOINT, PLATE_BOTTOM, 'left')" :fill="`url(#${id}-hatch-b)`" class="sketch-plate" />
    <polygon :points="plate(PLATE_JOINT, PLATE_BOTTOM, 'right')" :fill="`url(#${id}-hatch-b)`" class="sketch-plate" />

    <rect :x="CENTER - SHANK" :y="PLATE_TOP" :width="2 * SHANK" :height="NUT_BOTTOM + 12 - PLATE_TOP" class="sketch-bolt" />
    <rect :x="CENTER - HEAD" :y="HEAD_TOP" :width="2 * HEAD" :height="PLATE_TOP - HEAD_TOP" class="sketch-bolt" />
    <rect :x="CENTER - HEAD" :y="PLATE_BOTTOM" :width="2 * HEAD" :height="NUT_BOTTOM - PLATE_BOTTOM" class="sketch-nut" />
    <line :x1="CENTER" :x2="CENTER" :y1="HEAD_TOP - 8" :y2="NUT_BOTTOM + 20" class="sketch-axis" />

    <!-- Torque on the head. -->
    <path
      :d="`M ${CENTER - HEAD + 4} ${HEAD_TOP - 12} A ${HEAD + 6} 18 0 0 1 ${CENTER + HEAD - 4} ${HEAD_TOP - 12}`"
      :marker-end="`url(#${id}-arrow)`"
      class="sketch-force"
    />
    <text :x="CENTER" :y="HEAD_TOP - 34" text-anchor="middle" class="sketch-label">MA</text>

    <!-- Clamping force on both plates. -->
    <line :x1="PLATE_LEFT + 22" :x2="PLATE_LEFT + 22" :y1="PLATE_TOP - 30" :y2="PLATE_TOP - 2" :marker-end="`url(#${id}-arrow)`" class="sketch-force" />
    <line :x1="PLATE_LEFT + 22" :x2="PLATE_LEFT + 22" :y1="PLATE_BOTTOM + 30" :y2="PLATE_BOTTOM + 2" :marker-end="`url(#${id}-arrow)`" class="sketch-force" />
    <text :x="PLATE_LEFT + 30" :y="PLATE_TOP - 18" class="sketch-label">FV</text>
    <text :x="PLATE_LEFT + 30" :y="PLATE_BOTTOM + 24" class="sketch-label">FV</text>
  </svg>
</template>

<style scoped lang="scss">
.sketch {
  display: block;
  width: 100%;
  max-width: 260px;
  height: auto;
  margin: 0 auto;
}

.sketch-hatch {
  stroke: var(--p-text-muted-color);
  stroke-width: 1;
}

.sketch-plate {
  stroke: var(--p-text-color);
  stroke-width: 1.25;
}

.sketch-bolt {
  fill: var(--p-orange-500);
  fill-opacity: 0.3;
  stroke: var(--p-orange-500);
  stroke-width: 1.25;
}

.sketch-nut {
  fill: var(--p-blue-500);
  fill-opacity: 0.3;
  stroke: var(--p-blue-500);
  stroke-width: 1.25;
}

.sketch-axis {
  stroke: var(--p-text-muted-color);
  stroke-width: 1;
  stroke-dasharray: 12 3 2 3;
}

.sketch-force {
  fill: none;
  stroke: var(--p-primary-color);
  stroke-width: 2;
}

.sketch-arrowhead {
  fill: var(--p-primary-color);
}

.sketch-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
  fill: var(--p-primary-color);
}
</style>
