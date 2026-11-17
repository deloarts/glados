<script setup lang="ts">
/**
 * Side view from a control device or a guard opening to the hazard zone: a
 * two-hand console, a hand control, a foot pedal or a guard with its
 * opening, the reach D_DS or D_GT at hand height and the distance covered
 * during T. Both parts of S share one scale.
 */
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { numberOptions } from '../utils/safetyDistance/format'
import { roundUp } from '../utils/safetyDistance/inputs'
import type { SafetyDistanceInputs, SafetyDistanceResult } from '../utils/safetyDistance/types'
import SafetyDistanceSvgText from './SafetyDistanceSvgText.vue'

const props = defineProps<{ inputs: SafetyDistanceInputs; result: SafetyDistanceResult }>()

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()
const id = useId()

const P = 'tools.safetyDistance.sketch'

const GROUND = 176
const TOP = 40
const XD = 96
const XH = 372
const SEG_Y = 22
const S_Y = 196

type DeviceKind = 'twoHand' | 'hand' | 'foot' | 'guard'

function mm(value: number): string {
  return `${formatNumber(value, numberOptions(1))} mm`
}

const drawing = computed(() => {
  const inputs = props.inputs
  const r = props.result
  let kind: DeviceKind
  let reach: number | null
  let symbol = 'D_DS'
  let time = r.t
  if (inputs.mode === 'twoHand') {
    kind = 'twoHand'
    reach = inputs.twoHand.encroachmentPrevented ? 0 : 550
  } else if (inputs.mode === 'holdToRun') {
    kind = inputs.holdToRun.actuation
    reach = kind === 'foot' ? 2500 : 2200
  } else {
    kind = 'guard'
    symbol = 'D_GT'
    // D_GT as the calculation found it, from ISO 13857 or the own value.
    reach = r.steps.find((s) => s.key === 'reachThroughGuard')?.value ?? null
    const remaining = r.steps.find((s) => s.key === 'remainingTime')?.value
    if (inputs.guard.locking && remaining !== undefined) time = remaining
  }
  const timeDistance = time === null ? null : 1600 * time
  const s = r.s
  // Without T the reach is drawn over part of the way only, so it does not
  // look like all of S.
  const total = s ?? (timeDistance !== null ? (reach ?? 0) + timeDistance : (reach ?? 0) / 0.6)
  const px = (value: number) => ((XH - XD) * Math.max(0, value)) / Math.max(total, 1)
  const y = (h: number) => GROUND - (h / 2000) * (GROUND - TOP)

  const segments: { key: string; label: string; start: number; end: number; labelY: number }[] = []
  let x = XD
  let below = false
  const push = (key: string, label: string, value: number) => {
    const width = px(value)
    below = width < 90 ? !below : false
    segments.push({ key, label, start: x, end: x + width, labelY: below ? SEG_Y + 14 : SEG_Y - 6 })
    x += width
  }
  if (s !== null && reach !== null) {
    if (reach > 0) push('reach', `${symbol} = ${mm(reach)}`, reach)
    if (timeDistance !== null) {
      const label = inputs.mode === 'guard' && inputs.guard.locking ? 'K · (T − t_DY)' : 'K · T'
      push('time', `${label} = ${mm(timeDistance)}`, timeDistance)
    }
    const extra = s - reach - (timeDistance ?? 0)
    if (extra > 0.05) push('extra', `+ ${mm(extra)}`, extra)
  }

  const handY = y(1100)
  return {
    kind,
    handY,
    reachEnd: XD + px(reach ?? 0),
    segments,
    columnTop: handY + 16,
    person: { head: y(1650), shoulder: y(1420), hip: y(900) },
    // While fields are empty S stands on its own.
    sLabel:
      r.s !== null
        ? `S = ${mm(roundUp(r.s, 1))}`
        : r.messages.some((m) => m.level === 'error')
          ? `S: ${t(`${P}.labels.noResult`)}`
          : 'S',
    hazardTop: y(1300),
    hazardBottom: y(800),
    guardGapTop: handY - 9,
    guardGapBottom: handY + 9,
    guardTop: y(1800),
  }
})
</script>

<template>
  <figure class="sk" :data-testid="`sd-sketch-reach-${drawing.kind}`">
    <svg viewBox="0 0 444 216" class="sk-svg" role="img" :aria-label="t(`${P}.captions.${drawing.kind === 'guard' ? 'guard' : 'control'}`)">
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

      <!-- The device S is measured from -->
      <g class="sk-device">
        <template v-if="drawing.kind === 'twoHand'">
          <rect :x="XD - 26" :y="drawing.columnTop" width="12" :height="GROUND - drawing.columnTop" />
          <rect :x="XD - 46" :y="drawing.handY + 4" width="52" :height="drawing.columnTop - drawing.handY - 4" />
          <circle :cx="XD - 36" :cy="drawing.handY" r="4" />
          <circle :cx="XD" :cy="drawing.handY" r="4" />
        </template>
        <template v-else-if="drawing.kind === 'hand'">
          <rect :x="XD - 6" :y="drawing.columnTop" width="12" :height="GROUND - drawing.columnTop" />
          <rect :x="XD - 14" :y="drawing.handY + 4" width="28" :height="drawing.columnTop - drawing.handY - 4" />
          <circle :cx="XD" :cy="drawing.handY" r="4" />
        </template>
        <template v-else-if="drawing.kind === 'foot'">
          <path :d="`M ${XD - 22} ${GROUND} L ${XD + 4} ${GROUND} L ${XD + 4} ${GROUND - 5} L ${XD - 18} ${GROUND - 13} Z`" />
        </template>
        <template v-else>
          <rect :x="XD - 4" :y="drawing.guardTop" width="8" :height="drawing.guardGapTop - drawing.guardTop" :fill="`url(#${id}-hatch)`" />
          <rect :x="XD - 4" :y="drawing.guardGapBottom" width="8" :height="GROUND - drawing.guardGapBottom" :fill="`url(#${id}-hatch)`" />
        </template>
      </g>
      <!-- Someone standing on the pedal, the arm stretched out along the reach -->
      <g v-if="drawing.kind === 'foot'" class="sk-person">
        <circle :cx="XD - 30" :cy="drawing.person.head" r="7" />
        <line :x1="XD - 30" :x2="XD - 30" :y1="drawing.person.head + 7" :y2="drawing.person.hip" />
        <line :x1="XD - 30" :x2="XD" :y1="drawing.person.shoulder" :y2="drawing.handY" />
        <line :x1="XD - 30" :x2="XD - 10" :y1="drawing.person.hip" :y2="GROUND - 10" />
        <line :x1="XD - 30" :x2="XD - 44" :y1="drawing.person.hip" :y2="GROUND" />
      </g>
      <SafetyDistanceSvgText v-if="drawing.kind === 'guard'" text="e" :x="XD - 8" :y="drawing.handY + 4" text-anchor="end" class="sk-label" />
      <SafetyDistanceSvgText
        :text="t(`${P}.labels.${drawing.kind}`)"
        :x="drawing.kind === 'foot' ? XD - 62 : XD - 20"
        :y="drawing.kind === 'guard' ? drawing.guardTop - 6 : drawing.kind === 'foot' ? GROUND - 4 : drawing.handY - 10"
        text-anchor="middle"
        class="sk-label sk-label--halo"
      />

      <!-- Reach at hand height, then the hazard zone -->
      <line
        :x1="XD"
        :x2="drawing.reachEnd"
        :y1="drawing.handY"
        :y2="drawing.handY"
        :marker-end="drawing.reachEnd > XD + 4 ? `url(#${id}-arrow)` : undefined"
        class="sk-reach"
        data-testid="sd-sketch-reach-line"
      />
      <line :x1="drawing.reachEnd" :x2="drawing.reachEnd" :y1="SEG_Y + 4" :y2="GROUND" class="sk-ext" />
      <rect :x="XH" :y="drawing.hazardTop" width="40" :height="drawing.hazardBottom - drawing.hazardTop" :fill="`url(#${id}-cross)`" class="sk-hazard" />
      <SafetyDistanceSvgText :text="t(`${P}.labels.hazard`)" :x="XH + 20" :y="drawing.hazardBottom + 13" text-anchor="middle" class="sk-label sk-label--halo" />

      <!-- S and its parts -->
      <line :x1="XD" :x2="XD" :y1="SEG_Y - 6" :y2="S_Y + 4" class="sk-ext" />
      <line :x1="XH" :x2="XH" :y1="SEG_Y - 6" :y2="S_Y + 4" class="sk-ext" />
      <g v-for="seg in drawing.segments" :key="seg.key" :data-testid="`sd-sketch-seg-${seg.key}`">
        <line :x1="seg.start" :x2="seg.end" :y1="SEG_Y" :y2="SEG_Y" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
        <SafetyDistanceSvgText :text="seg.label" :x="(seg.start + seg.end) / 2" :y="seg.labelY" text-anchor="middle" class="sk-label sk-label--halo" />
      </g>
      <line :x1="XD" :x2="XH" :y1="S_Y" :y2="S_Y" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
      <SafetyDistanceSvgText :text="drawing.sLabel" :x="(XD + XH) / 2" :y="S_Y + 15" text-anchor="middle" class="sk-label sk-label--strong" data-testid="sd-sketch-s" />
    </svg>
    <figcaption class="sk-caption">{{ t(`${P}.captions.${drawing.kind === 'guard' ? 'guard' : 'control'}`) }}</figcaption>
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

.sk-device {
  fill: var(--p-content-background);
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
  stroke: var(--p-text-color);
  stroke-width: 2.25;
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
