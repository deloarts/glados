<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useFitFormat } from '../composables/useFitFormat'

interface Zone {
  upper: number
  lower: number
}

const props = defineProps<{
  holeCode: string
  shaftCode: string
  hole: Zone
  shaft: Zone
}>()

const { t } = useI18n()
const fmt = useFitFormat()

// Compact enough to stay legible in a third of a wide screen, next to the
// limits sketches.
const WIDTH = 380
const HEIGHT = 380
const TOP = 24
const PLOT_HEIGHT = 332
const HOLE_X = 105
const SHAFT_X = 215
const ZONE_WIDTH = 90

// Both zones and the zero line share one vertical scale, padded so a zone
// never touches the edge of the drawing.
const geometry = computed(() => {
  const hi = Math.max(0, props.hole.upper, props.shaft.upper)
  const lo = Math.min(0, props.hole.lower, props.shaft.lower)
  const pad = (hi - lo || 1) * 0.12
  const top = hi + pad
  const bottom = lo - pad
  const y = (value: number) => TOP + ((top - value) / (top - bottom)) * PLOT_HEIGHT
  const zone = (z: Zone) => {
    const yTop = y(z.upper)
    const yBottom = y(z.lower)
    return { y: yTop, height: Math.max(2, yBottom - yTop), mid: (yTop + yBottom) / 2, yTop, yBottom }
  }
  return { zero: y(0), hole: zone(props.hole), shaft: zone(props.shaft) }
})
</script>

<template>
  <section class="zone">
    <h3 class="zone-title">{{ t('tools.fitCalculator.diagram.title') }}</h3>
    <div class="zone-card">
      <div class="zone-plot">
        <svg
          :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
          role="img"
          :aria-label="t('tools.fitCalculator.diagram.aria')"
          class="zone-svg"
        >
          <line x1="40" :x2="WIDTH - 20" :y1="geometry.zero" :y2="geometry.zero" class="zone-zero" />
          <text x="36" :y="geometry.zero + 4" text-anchor="end" class="zone-text">0</text>

          <rect
            :x="HOLE_X"
            :y="geometry.hole.y"
            :width="ZONE_WIDTH"
            :height="geometry.hole.height"
            rx="3"
            class="zone-rect zone-rect--hole"
          />
          <text :x="HOLE_X + ZONE_WIDTH / 2" :y="geometry.hole.mid + 5" text-anchor="middle" class="zone-code">
            {{ holeCode }}
          </text>
          <text :x="HOLE_X - 8" :y="geometry.hole.yTop + 4" text-anchor="end" class="zone-text zone-text--hole">
            {{ fmt.deviationUm(hole.upper) }}
          </text>
          <text :x="HOLE_X - 8" :y="geometry.hole.yBottom + 4" text-anchor="end" class="zone-text zone-text--hole">
            {{ fmt.deviationUm(hole.lower) }}
          </text>

          <rect
            :x="SHAFT_X"
            :y="geometry.shaft.y"
            :width="ZONE_WIDTH"
            :height="geometry.shaft.height"
            rx="3"
            class="zone-rect zone-rect--shaft"
          />
          <text :x="SHAFT_X + ZONE_WIDTH / 2" :y="geometry.shaft.mid + 5" text-anchor="middle" class="zone-code">
            {{ shaftCode }}
          </text>
          <text :x="SHAFT_X + ZONE_WIDTH + 8" :y="geometry.shaft.yTop + 4" class="zone-text zone-text--shaft">
            {{ fmt.deviationUm(shaft.upper) }}
          </text>
          <text :x="SHAFT_X + ZONE_WIDTH + 8" :y="geometry.shaft.yBottom + 4" class="zone-text zone-text--shaft">
            {{ fmt.deviationUm(shaft.lower) }}
          </text>
        </svg>
      </div>
      <footer class="zone-footer">
        <span class="zone-legend"><span class="zone-swatch zone-swatch--hole" />{{ t('tools.fitCalculator.hole') }}</span>
        <span class="zone-legend"><span class="zone-swatch zone-swatch--shaft" />{{ t('tools.fitCalculator.shaft') }}</span>
        <span class="zone-scale">{{ t('tools.fitCalculator.diagram.scale') }}</span>
      </footer>
    </div>
  </section>
</template>

<style scoped lang="scss">
.zone {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
}

// Framed like the hole and shaft sketches next to it, and stretched to their
// height so the boxes line up.
.zone-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.zone-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  column-gap: var(--space-4);
  row-gap: var(--space-1);
}

.zone-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.zone-legend {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.zone-swatch {
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 3px;

  &--hole {
    background: var(--p-blue-500);
  }

  &--shaft {
    background: var(--p-orange-500);
  }
}

.zone-scale {
  flex-basis: 100%;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

// The drawing takes whatever height the box has: next to the hole and shaft
// sketches their height sets the row, and the diagram scales into it (centred,
// aspect kept), so all three boxes end level. On its own it keeps a minimum.
.zone-plot {
  position: relative;
  flex: 1;
  min-height: 18rem;
}

.zone-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.zone-zero {
  stroke: var(--p-text-color);
  stroke-width: 1.5;
}

.zone-rect {
  stroke-width: 1.5;
  fill-opacity: 0.35;

  &--hole {
    fill: var(--p-blue-500);
    stroke: var(--p-blue-500);
  }

  &--shaft {
    fill: var(--p-orange-500);
    stroke: var(--p-orange-500);
  }
}

.zone-code {
  font-size: var(--font-size-sm);
  font-weight: 600;
  fill: var(--p-text-color);
}

// The halo in the card colour masks the zero line behind a label that sits on
// it, such as the "0 µm" of an H hole.
.zone-text {
  font-size: var(--font-size-sm);
  fill: var(--p-text-muted-color);
  font-variant-numeric: tabular-nums;
  paint-order: stroke;
  stroke: var(--p-content-background);
  stroke-width: 4px;
  stroke-linejoin: round;

  &--hole {
    fill: var(--p-blue-500);
  }

  &--shaft {
    fill: var(--p-orange-500);
  }
}
</style>
