<script setup lang="ts">
/**
 * Section through a protective structure with a regular opening, not to
 * scale: the limb that fits through the opening e reaches as far as the
 * safety distance s_r, and the hazard zone has to lie beyond it. A distance
 * as built is marked where it falls short.
 */
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { numberOptions } from '../utils/safetyDistance/format'
import { roundUp } from '../utils/safetyDistance/inputs'
import type { OpeningInputs, SafetyDistanceResult } from '../utils/safetyDistance/types'
import { lookupOpening } from '../utils/safetyDistance/iso13857'
import { openingTable } from '../utils/safetyDistance/reach'
import SafetyDistanceSvgText from './SafetyDistanceSvgText.vue'

const props = defineProps<{ inputs: OpeningInputs; result: SafetyDistanceResult }>()

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()
const id = useId()

const P = 'tools.safetyDistance.sketch'

const WALL = 120
const MID = 104
const HAZARD = 360

function mm(value: number): string {
  return `${formatNumber(value, numberOptions(1))} mm`
}

const drawing = computed(() => {
  const inp = props.inputs
  const sr = props.result.s
  const e = inp.size
  const row = e === null ? null : lookupOpening(openingTable(inp), inp.shape, e)
  const part = row === null ? null : (openingTable(inp).rows[row.row]?.part ?? null)
  // The limb reaches up to the hazard when nothing as built is known; with a
  // distance as built the hazard moves to where it is, short of s_r or past it.
  const short = sr !== null && inp.distance !== null && inp.distance < sr
  const failed = props.result.messages.some((m) => m.level === 'error' && m.code !== 'openingTooClose')
  const reachEnd = short ? HAZARD + 26 : HAZARD - 2
  const gap = e === null ? 12 : Math.min(36, Math.max(6, 6 + e / 4))
  return {
    gapTop: MID - gap / 2,
    gapBottom: MID + gap / 2,
    reachEnd,
    part: part === null ? '' : t(`tools.safetyDistance.parts.${part}`),
    lower: inp.limb === 'lower',
    eLabel: e === null ? 'e' : `e = ${mm(e)}`,
    srLabel: sr !== null ? `s_r = ${mm(roundUp(sr, 1))}` : failed ? `s_r: ${t(`${P}.labels.noResult`)}` : 's_r',
    builtLabel: inp.distance === null ? null : t(`${P}.labels.asBuilt`, { value: mm(inp.distance) }),
    short,
  }
})
</script>

<template>
  <figure class="sk" data-testid="sd-sketch-opening">
    <svg viewBox="0 0 444 200" class="sk-svg" role="img" :aria-label="t(`${P}.captions.opening`)">
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

      <!-- The structure in section, with the opening -->
      <rect :x="WALL - 8" y="20" width="16" :height="drawing.gapTop - 20" :fill="`url(#${id}-hatch)`" class="sk-structure" />
      <rect :x="WALL - 8" :y="drawing.gapBottom" width="16" :height="170 - drawing.gapBottom" :fill="`url(#${id}-hatch)`" class="sk-structure" />
      <line :x1="WALL - 22" :x2="WALL - 22" :y1="drawing.gapTop - 14" :y2="drawing.gapTop" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
      <line :x1="WALL - 22" :x2="WALL - 22" :y1="drawing.gapBottom + 14" :y2="drawing.gapBottom" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
      <SafetyDistanceSvgText :text="drawing.eLabel" :x="WALL - 28" :y="MID + 4" text-anchor="end" class="sk-label sk-label--halo" data-testid="sd-sketch-e" />

      <!-- The limb through the opening, as far as it reaches -->
      <path
        :d="`M 20 ${MID - 9} L ${drawing.reachEnd - 8} ${MID - 4} Q ${drawing.reachEnd} ${MID} ${drawing.reachEnd - 8} ${MID + 4} L 20 ${MID + 9}`"
        class="sk-limb"
      />
      <SafetyDistanceSvgText v-if="drawing.part" :text="drawing.part" x="24" :y="MID - 16" class="sk-label sk-label--halo" data-testid="sd-sketch-part" />

      <!-- The hazard zone -->
      <rect :x="HAZARD" y="72" width="44" height="64" :fill="`url(#${id}-cross)`" class="sk-hazard" />
      <SafetyDistanceSvgText :text="t(`${P}.labels.hazard`)" :x="HAZARD + 22" y="150" text-anchor="middle" class="sk-label sk-label--halo" />

      <!-- s_r from the opening to the hazard zone -->
      <line :x1="WALL + 8" :x2="WALL + 8" y1="20" y2="40" class="sk-ext" />
      <line :x1="HAZARD" :x2="HAZARD" y1="20" y2="72" class="sk-ext" :class="{ 'sk-ext--short': drawing.short }" />
      <line :x1="WALL + 8" :x2="HAZARD" y1="30" y2="30" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
      <SafetyDistanceSvgText :text="drawing.srLabel" :x="(WALL + HAZARD) / 2 + 4" y="24" text-anchor="middle" class="sk-label sk-label--strong" data-testid="sd-sketch-sr" />
      <SafetyDistanceSvgText
        v-if="drawing.builtLabel"
        :text="drawing.builtLabel"
        :x="HAZARD + 22"
        y="166"
        text-anchor="middle"
        class="sk-label"
        :class="{ 'sk-label--alert': drawing.short }"
        data-testid="sd-sketch-built"
      />
    </svg>
    <figcaption class="sk-caption">{{ t(`${P}.captions.${drawing.lower ? 'openingLower' : 'opening'}`) }}</figcaption>
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

.sk-structure,
.sk-hazard {
  stroke: var(--p-text-color);
  stroke-width: 1.25;
}

.sk-limb {
  fill: var(--p-content-background);
  stroke: var(--p-text-muted-color);
  stroke-width: 2;
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
