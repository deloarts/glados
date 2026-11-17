<script setup lang="ts">
/**
 * Side view of reaching over a protective structure, to scale: the structure
 * of height h_ps, the arm reaching over its top edge and the hazard zone at
 * height h_h behind it, at the safety distance s_h. A distance as built is
 * drawn where it is and measured against s_h.
 */
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { numberOptions } from '../utils/safetyDistance/format'
import { roundUp } from '../utils/safetyDistance/inputs'
import type { SafetyDistanceResult, StructureInputs } from '../utils/safetyDistance/types'
import SafetyDistanceSvgText from './SafetyDistanceSvgText.vue'

const props = defineProps<{ inputs: StructureInputs; result: SafetyDistanceResult }>()

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()
const id = useId()

const P = 'tools.safetyDistance.sketch'

const GROUND = 206
const TOP = 26
const XS = 150
const RIGHT = 420

function mm(value: number): string {
  return `${formatNumber(value, numberOptions(1))} mm`
}

const drawing = computed(() => {
  const inp = props.inputs
  const sh = props.result.s
  // Empty fields are drawn with typical proportions and labelled by symbol only.
  const hps = inp.structureHeight ?? 1600
  const hh = inp.hazardHeight ?? 1200
  const placed = inp.distance ?? sh ?? 800
  const maxHeight = Math.max(2800, hps + 300, hh + 300)
  const y = (h: number) => GROUND - (Math.max(0, h) / maxHeight) * (GROUND - TOP)
  const span = Math.max(placed, sh ?? 0, 600)
  const px = (value: number) => ((RIGHT - XS - 40) * Math.max(0, value)) / span

  const hazardX = XS + px(placed)
  const hazardY = y(hh)
  const failed = props.result.messages.some((m) => m.level === 'error' && m.code !== 'structureTooClose')
  const required = sh === null ? null : XS + px(sh)
  const short = sh !== null && inp.distance !== null && inp.distance < sh

  return {
    structureTop: y(hps),
    hazardX,
    hazardY,
    required,
    short,
    shoulder: { x: XS - 46, y: y(1450) },
    head: { x: XS - 46, y: y(1650) },
    hip: y(950),
    hpsLabel: inp.structureHeight === null ? 'h_ps' : `h_ps = ${mm(inp.structureHeight)}`,
    hhLabel: inp.hazardHeight === null ? 'h_h' : `h_h = ${mm(inp.hazardHeight)}`,
    shLabel:
      sh !== null ? `s_h = ${mm(roundUp(sh, 1))}` : failed ? `s_h: ${t(`${P}.labels.noResult`)}` : 's_h',
    builtLabel: inp.distance === null ? null : t(`${P}.labels.asBuilt`, { value: mm(inp.distance) }),
  }
})
</script>

<template>
  <figure class="sk" data-testid="sd-sketch-structure">
    <svg viewBox="0 0 444 246" class="sk-svg" role="img" :aria-label="t(`${P}.captions.structure`)">
      <defs>
        <pattern :id="`${id}-hatch`" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" class="sk-hatch" />
        </pattern>
        <pattern :id="`${id}-cross`" patternUnits="userSpaceOnUse" width="6" height="6">
          <path d="M0 0 L6 6 M6 0 L0 6" class="sk-hatch" />
        </pattern>
        <marker :id="`${id}-arrow`" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" class="sk-arrowhead" />
        </marker>
      </defs>

      <rect x="8" :y="GROUND" width="428" height="7" :fill="`url(#${id}-hatch)`" class="sk-none" />
      <line x1="8" x2="436" :y1="GROUND" :y2="GROUND" class="sk-ground" />

      <!-- The protective structure and its height -->
      <rect :x="XS - 4" :y="drawing.structureTop" width="8" :height="GROUND - drawing.structureTop" :fill="`url(#${id}-hatch)`" class="sk-structure" />
      <line :x1="XS + 14" :x2="XS + 14" :y1="GROUND" :y2="drawing.structureTop" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
      <SafetyDistanceSvgText :text="drawing.hpsLabel" :x="XS + 18" :y="drawing.structureTop + 14" class="sk-label sk-label--halo" data-testid="sd-sketch-hps" />

      <!-- Someone reaching over the top edge -->
      <g class="sk-person">
        <circle :cx="drawing.head.x" :cy="drawing.head.y" r="7" />
        <line :x1="drawing.head.x" :x2="drawing.head.x" :y1="drawing.head.y + 7" :y2="drawing.hip" />
        <line :x1="drawing.head.x" :x2="drawing.head.x - 12" :y1="drawing.hip" :y2="GROUND" />
        <line :x1="drawing.head.x" :x2="drawing.head.x + 8" :y1="drawing.hip" :y2="GROUND" />
      </g>
      <polyline
        :points="`${drawing.shoulder.x},${drawing.shoulder.y} ${XS},${drawing.structureTop - 4} ${drawing.hazardX},${drawing.hazardY}`"
        class="sk-reach"
        :marker-end="`url(#${id}-arrow)`"
      />

      <!-- The hazard zone at its height, with that height -->
      <rect :x="drawing.hazardX" :y="drawing.hazardY - 10" width="34" height="20" :fill="`url(#${id}-cross)`" class="sk-hazard" />
      <line :x1="drawing.hazardX + 44" :x2="drawing.hazardX + 44" :y1="GROUND" :y2="drawing.hazardY" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
      <SafetyDistanceSvgText :text="drawing.hhLabel" :x="drawing.hazardX + 40" :y="drawing.hazardY - 16" text-anchor="end" class="sk-label sk-label--halo" data-testid="sd-sketch-hh" />

      <!-- s_h, and the distance as built where it falls short -->
      <line :x1="XS" :x2="XS" :y1="GROUND" :y2="GROUND + 24" class="sk-ext" />
      <template v-if="drawing.required !== null">
        <line :x1="drawing.required" :x2="drawing.required" :y1="drawing.hazardY" :y2="GROUND + 24" class="sk-ext" :class="{ 'sk-ext--short': drawing.short }" />
        <line :x1="XS" :x2="drawing.required" :y1="GROUND + 18" :y2="GROUND + 18" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
      </template>
      <SafetyDistanceSvgText :text="drawing.shLabel" :x="XS + 6" :y="GROUND + 34" class="sk-label sk-label--strong" data-testid="sd-sketch-sh" />
      <SafetyDistanceSvgText
        v-if="drawing.builtLabel"
        :text="drawing.builtLabel"
        :x="drawing.hazardX + 17"
        :y="drawing.hazardY + 24"
        text-anchor="middle"
        class="sk-label sk-label--halo"
        :class="{ 'sk-label--alert': drawing.short }"
        data-testid="sd-sketch-built"
      />
    </svg>
    <figcaption class="sk-caption">{{ t(`${P}.captions.structure`) }}</figcaption>
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

.sk-none {
  stroke: none;
}

.sk-hatch {
  stroke: var(--p-text-muted-color);
  stroke-width: 1;
}

.sk-ground {
  stroke: var(--p-text-color);
  stroke-width: 1.5;
}

.sk-structure,
.sk-hazard {
  stroke: var(--p-text-color);
  stroke-width: 1.25;
}

.sk-person {
  fill: none;
  stroke: var(--p-text-muted-color);
  stroke-width: 2;
  stroke-linecap: round;
}

.sk-reach {
  fill: none;
  stroke: var(--p-text-color);
  stroke-width: 2.25;
  stroke-linejoin: round;
}

.sk-dim {
  stroke: var(--p-text-color);
  stroke-width: 1;
}

.sk-ext {
  stroke: var(--p-text-muted-color);
  stroke-width: 0.75;
  stroke-dasharray: 3 3;

  &--short {
    stroke: var(--p-red-500);
  }
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
