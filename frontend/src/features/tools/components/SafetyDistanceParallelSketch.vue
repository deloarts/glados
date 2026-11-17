<script setup lang="ts">
/**
 * Side view of a detection zone approached in parallel: a person walking
 * towards the zone at height H_D with depth F_D, the gap G_D to the machine,
 * and S from the far edge of the zone to the hazard, split into the reach of
 * 1200 mm and the distance covered during T. Lengths share one scale.
 */
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { numberOptions } from '../utils/safetyDistance/format'
import { roundUp } from '../utils/safetyDistance/inputs'
import type { ParallelInputs, SafetyDistanceResult } from '../utils/safetyDistance/types'
import SafetyDistanceSvgText from './SafetyDistanceSvgText.vue'

const props = defineProps<{ inputs: ParallelInputs; result: SafetyDistanceResult }>()

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()
const id = useId()

const P = 'tools.safetyDistance.sketch'

const GROUND = 196
const TOP = 52
const XF = 84
const XEND = 424
const SEG_Y = 22
const S_Y = 218
/** Assumed gap when none is entered, so the machine face still has a place. */
const UNKNOWN_GAP = 100
const REACH = 1200

function mm(value: number): string {
  return `${formatNumber(value, numberOptions(1))} mm`
}

const drawing = computed(() => {
  const p = props.inputs
  const r = props.result
  const required = r.steps.find((s) => s.key === 'requiredDepth')?.value ?? REACH
  const sStep = r.steps.find((s) => s.key === 'separation')?.value ?? null
  const s = r.s ?? sStep
  const hd = p.fieldHeight ?? 0
  const depth = p.fieldDepth ?? required
  const gap = p.obstacleGap ?? UNKNOWN_GAP
  const timeDistance = r.t === null ? null : 1600 * r.t + (r.supplement ?? 0)

  const vy = (GROUND - TOP) / 1900
  const y = (h: number) => GROUND - Math.max(0, h) * vy
  const total = Math.max(s ?? 0, depth + gap) * 1.08
  const px = (value: number) => ((XEND - XF) * Math.max(0, value)) / Math.max(total, 1)

  const fieldEnd = XF + px(depth)
  const machine = Math.max(fieldEnd + 4, XF + px(depth + gap))
  // Without a result S runs schematically to the hazard.
  const sEnd = s !== null ? XF + px(s) : machine + 6
  const hazard = Math.max(sEnd, machine + 6)

  const segments: { key: string; label: string; start: number; end: number }[] = []
  if (s !== null) {
    const reachEnd = XF + px(REACH)
    segments.push({ key: 'reach', label: `D_DS = ${mm(REACH)}`, start: XF, end: reachEnd })
    if (timeDistance !== null) {
      const symbol = (r.supplement ?? 0) > 0 ? 'K · T + Z' : 'K · T'
      segments.push({ key: 'time', label: `${symbol} = ${mm(timeDistance)}`, start: reachEnd, end: sEnd })
    }
  }

  return {
    fieldY: y(hd) - 6,
    hd,
    hdY: y(hd),
    fieldEnd,
    machine,
    machineTop: y(1500),
    hazard,
    hazardTop: y(1150),
    hazardBottom: y(850),
    sEnd,
    segments,
    depthLabel: p.fieldDepth === null ? `F_D ≥ ${mm(required)}` : `F_D = ${mm(depth)}`,
    gapLabel: p.obstacleGap === null ? 'G_D' : `G_D = ${mm(gap)}`,
    // While fields are empty S stands on its own.
    sLabel:
      r.s !== null
        ? `S = ${mm(roundUp(r.s, 1))}`
        : r.messages.some((m) => m.level === 'error')
          ? `S: ${t(`${P}.labels.noResult`)}`
          : 'S',
    person: { head: y(1620), shoulder: y(1450), hip: y(900) },
  }
})
</script>

<template>
  <figure class="sk" data-testid="sd-sketch-parallel">
    <svg viewBox="0 0 444 238" class="sk-svg" role="img" :aria-label="t(`${P}.captions.parallel`)">
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

      <!-- A person walking towards the zone -->
      <g class="sk-person">
        <circle cx="40" :cy="drawing.person.head" r="7" />
        <line x1="40" x2="40" :y1="drawing.person.head + 7" :y2="drawing.person.hip" />
        <line x1="40" x2="54" :y1="drawing.person.shoulder" :y2="drawing.person.shoulder + 26" />
        <line x1="40" x2="30" :y1="drawing.person.shoulder" :y2="drawing.person.shoulder + 30" />
        <line x1="40" x2="52" :y1="drawing.person.hip" :y2="GROUND" />
        <line x1="40" x2="28" :y1="drawing.person.hip" :y2="GROUND" />
      </g>
      <line x1="22" x2="64" :y1="drawing.person.head - 16" :y2="drawing.person.head - 16" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />

      <!-- Detection zone at H_D with depth F_D -->
      <rect :x="XF" :y="drawing.fieldY" :width="drawing.fieldEnd - XF" height="6" class="sk-field" data-testid="sd-sketch-field" />
      <template v-if="drawing.hd > 0">
        <line :x1="XF - 14" :x2="XF - 14" :y1="GROUND" :y2="drawing.hdY" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
        <SafetyDistanceSvgText
          :text="`H_D = ${mm(drawing.hd)}`"
          :x="XF - 18"
          :y="GROUND - 3"
          text-anchor="start"
          :transform="`rotate(-90 ${XF - 18} ${GROUND - 3})`"
          class="sk-label sk-label--halo"
        />
      </template>
      <line :x1="XF" :x2="drawing.fieldEnd" :y1="drawing.fieldY - 14" :y2="drawing.fieldY - 14" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
      <SafetyDistanceSvgText :text="drawing.depthLabel" :x="(XF + drawing.fieldEnd) / 2" :y="drawing.fieldY - 19" text-anchor="middle" class="sk-label sk-label--halo" data-testid="sd-sketch-depth" />
      <line :x1="drawing.fieldEnd" :x2="drawing.machine" :y1="drawing.fieldY - 14" :y2="drawing.fieldY - 14" class="sk-dim" />
      <SafetyDistanceSvgText :text="drawing.gapLabel" :x="drawing.machine + 4" :y="drawing.fieldY - 26" text-anchor="end" class="sk-label sk-label--halo" />

      <!-- Machine with the hazard zone -->
      <rect :x="drawing.machine" :y="drawing.machineTop" :width="436 - drawing.machine" :height="GROUND - drawing.machineTop" class="sk-machine" />
      <SafetyDistanceSvgText :text="t(`${P}.labels.machine`)" :x="drawing.machine + 6" :y="drawing.machineTop + 14" class="sk-label sk-label--muted" />
      <rect
        :x="drawing.hazard"
        :y="drawing.hazardTop"
        width="22"
        :height="drawing.hazardBottom - drawing.hazardTop"
        :fill="`url(#${id}-cross)`"
        class="sk-hazard"
      />
      <SafetyDistanceSvgText :text="t(`${P}.labels.hazard`)" :x="drawing.hazard + 11" :y="drawing.hazardBottom + 13" text-anchor="middle" class="sk-label sk-label--halo" />

      <!-- S from the far edge of the zone, and its parts -->
      <line :x1="XF" :x2="XF" :y1="SEG_Y - 6" :y2="S_Y + 4" class="sk-ext" />
      <line :x1="drawing.sEnd" :x2="drawing.sEnd" :y1="SEG_Y - 6" :y2="S_Y + 4" class="sk-ext" />
      <g v-for="seg in drawing.segments" :key="seg.key">
        <line :x1="seg.start" :x2="seg.end" :y1="SEG_Y" :y2="SEG_Y" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
        <SafetyDistanceSvgText :text="seg.label" :x="(seg.start + seg.end) / 2" :y="SEG_Y + 13" text-anchor="middle" class="sk-label sk-label--halo" />
      </g>
      <line :x1="XF" :x2="drawing.sEnd" :y1="S_Y" :y2="S_Y" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
      <SafetyDistanceSvgText :text="drawing.sLabel" :x="(XF + drawing.sEnd) / 2" :y="S_Y + 15" text-anchor="middle" class="sk-label sk-label--strong" data-testid="sd-sketch-s" />
    </svg>
    <figcaption class="sk-caption">{{ t(`${P}.captions.parallel`) }}</figcaption>
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

.sk-person {
  fill: none;
  stroke: var(--p-text-muted-color);
  stroke-width: 2;
  stroke-linecap: round;
}

// Dashed outline and a light fill, so the zone reads without colour too.
.sk-field {
  fill: var(--p-primary-color);
  fill-opacity: 0.25;
  stroke: var(--p-primary-color);
  stroke-width: 1.5;
  stroke-dasharray: 4 2;
}

.sk-machine {
  fill: none;
  stroke: var(--p-text-color);
  stroke-width: 1.25;
}

.sk-hazard {
  stroke: var(--p-text-color);
  stroke-width: 1.25;
}

.sk-dim {
  stroke: var(--p-text-color);
  stroke-width: 1;
}

.sk-ext {
  stroke: var(--p-text-muted-color);
  stroke-width: 0.75;
  stroke-dasharray: 3 3;
}

.sk-arrowhead {
  fill: var(--p-text-color);
}

.sk-label {
  font-size: var(--font-size-xs);
  fill: var(--p-text-color);
  font-variant-numeric: tabular-nums;

  &--muted {
    fill: var(--p-text-muted-color);
  }

  &--strong {
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
