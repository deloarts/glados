<script setup lang="ts">
/**
 * A crushing point, not to scale: a moving part closing on a fixed one, the
 * body part between them and the minimum gap a that has to stay open. A gap
 * as built is set against it.
 */
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { numberOptions } from '../utils/safetyDistance/format'
import type { CrushingInputs, SafetyDistanceResult } from '../utils/safetyDistance/types'
import SafetyDistanceSvgText from './SafetyDistanceSvgText.vue'

const props = defineProps<{ inputs: CrushingInputs; result: SafetyDistanceResult }>()

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()
const id = useId()

const P = 'tools.safetyDistance.sketch'
const F = 'tools.safetyDistance.fields'

const FIXED_Y = 150
const LEFT = 96
const RIGHT = 316

function mm(value: number): string {
  return `${formatNumber(value, numberOptions(1))} mm`
}

const drawing = computed(() => {
  const inp = props.inputs
  const a = props.result.s
  const short = a !== null && inp.gap !== null && inp.gap < a
  // The gap opens wider for larger body parts, so the drawing reads at a glance.
  const height = a === null ? 50 : Math.min(84, Math.max(26, 18 + Math.sqrt(a) * 3))
  return {
    movingY: FIXED_Y - height,
    part: inp.bodyPart === null ? '' : t(`${F}.bodyPart.${inp.bodyPart}`),
    aLabel: a === null ? 'a' : `a ≥ ${mm(a)}`,
    builtLabel: inp.gap === null ? null : t(`${P}.labels.asBuilt`, { value: mm(inp.gap) }),
    short,
  }
})
</script>

<template>
  <figure class="sk" data-testid="sd-sketch-crushing">
    <svg viewBox="0 0 444 196" class="sk-svg" role="img" :aria-label="t(`${P}.captions.crushing`)">
      <defs>
        <pattern :id="`${id}-hatch`" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" class="sk-hatch" />
        </pattern>
        <marker :id="`${id}-arrow`" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" class="sk-arrowhead" />
        </marker>
      </defs>

      <!-- Moving part above, with its direction, and the fixed part below -->
      <rect :x="LEFT" :y="drawing.movingY - 34" :width="RIGHT - LEFT" height="34" class="sk-part" />
      <line :x1="(LEFT + RIGHT) / 2" :x2="(LEFT + RIGHT) / 2" :y1="drawing.movingY - 58" :y2="drawing.movingY - 38" :marker-end="`url(#${id}-arrow)`" class="sk-motion" />
      <SafetyDistanceSvgText :text="t(`${P}.labels.moving`)" :x="(LEFT + RIGHT) / 2 + 8" :y="drawing.movingY - 44" class="sk-label sk-label--halo" />
      <rect :x="LEFT" :y="FIXED_Y" :width="RIGHT - LEFT" height="28" :fill="`url(#${id}-hatch)`" class="sk-part" />

      <!-- The body part in the gap -->
      <ellipse :cx="LEFT + 70" :cy="(drawing.movingY + FIXED_Y) / 2" rx="58" :ry="(FIXED_Y - drawing.movingY) / 2 - 4" class="sk-body" />
      <SafetyDistanceSvgText v-if="drawing.part" :text="drawing.part" :x="LEFT + 70" :y="(drawing.movingY + FIXED_Y) / 2 + 4" text-anchor="middle" class="sk-label" data-testid="sd-sketch-part" />

      <!-- The gap a -->
      <line :x1="RIGHT - 40" :x2="RIGHT - 40" :y1="drawing.movingY" :y2="FIXED_Y" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
      <SafetyDistanceSvgText :text="drawing.aLabel" :x="RIGHT + 8" :y="(drawing.movingY + FIXED_Y) / 2" class="sk-label sk-label--strong" data-testid="sd-sketch-a" />
      <SafetyDistanceSvgText
        v-if="drawing.builtLabel"
        :text="drawing.builtLabel"
        :x="RIGHT + 8"
        :y="(drawing.movingY + FIXED_Y) / 2 + 15"
        class="sk-label"
        :class="{ 'sk-label--alert': drawing.short }"
        data-testid="sd-sketch-built"
      />
    </svg>
    <figcaption class="sk-caption">{{ t(`${P}.captions.crushing`) }}</figcaption>
  </figure>
</template>

<style scoped lang="scss">
.sk {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.sk-svg {
  display: block;
  width: 100%;
  max-width: 40rem;
  height: auto;
}

.sk-caption {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  line-height: 1.4;
}

.sk-hatch {
  stroke: var(--p-text-muted-color);
  stroke-width: 1;
}

.sk-part {
  fill: var(--p-content-background);
  stroke: var(--p-text-color);
  stroke-width: 1.25;
}

.sk-body {
  fill: var(--p-content-background);
  stroke: var(--p-text-muted-color);
  stroke-width: 2;
}

.sk-motion {
  stroke: var(--p-text-color);
  stroke-width: 1.5;
}

.sk-dim {
  stroke: var(--p-text-color);
  stroke-width: 1;
}

.sk-arrowhead {
  fill: var(--p-text-color);
}

.sk-label {
  font-size: var(--font-size-xs);
  fill: var(--p-text-color);
  font-variant-numeric: tabular-nums;

  &--strong {
    font-weight: 700;
  }

  &--alert {
    fill: var(--p-red-500);
    font-weight: 700;
  }

  &--halo {
    paint-order: stroke;
    stroke: var(--p-content-background);
    stroke-width: 3px;
    stroke-linejoin: round;
  }
}
</style>
