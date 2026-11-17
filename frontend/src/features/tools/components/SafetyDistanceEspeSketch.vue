<script setup lang="ts">
/**
 * Side view of a light curtain approached at a right angle: the field
 * between H_DB and H_DT, the hazard at H_H, the three ways past the field
 * as arrows and S split into the largest reach distance and the distance
 * covered during T. Heights share one scale taken from the inputs; the
 * horizontal distances share another taken from the result, so a short S
 * stays readable next to a tall field.
 */
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { numberOptions } from '../utils/safetyDistance/format'
import { roundUp } from '../utils/safetyDistance/inputs'
import type { EspeInputs, ReachPath, SafetyDistanceResult } from '../utils/safetyDistance/types'
import SafetyDistanceSvgText from './SafetyDistanceSvgText.vue'

const props = defineProps<{ inputs: EspeInputs; result: SafetyDistanceResult }>()

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()
const id = useId()

const P = 'tools.safetyDistance.sketch'

const GROUND = 212
const TOP = 60
const XC = 112
const XR = 380
const HAZARD_RIGHT = 414
const SEG_Y = 34
const S_Y = 238
/** Schematic height of a structure above the field, which the inputs do not give. */
const STRUCTURE_HEIGHT = 400

const SYMBOLS: Record<ReachPath, string> = {
  over: 'D_DO',
  through: 'D_DT',
  under: 'D_DU',
  overStructure: 'D_GO',
  underStructure: 'D_GU',
}

const COMBINED_STEPS = new Set(['withHandSpeed', 'withWalkingSpeed', 'minimum', 'minimumAndSupplement', 'publicSupplement'])

function mm(value: number): string {
  return `${formatNumber(value, numberOptions(1))} mm`
}

const drawing = computed(() => {
  const e = props.inputs
  const r = props.result
  // Empty heights are drawn at typical values and labelled without a number.
  const hdt = e.topEdge ?? 1800
  const hdb = e.bottomEdge ?? 300
  const gap = e.structureGap ?? 0
  const hh = e.hazardHeight ?? 1000
  const maxHeight = Math.max(1000, hdt + (e.structureAbove ? STRUCTURE_HEIGHT : 0), hh) * 1.1
  const y = (h: number) => GROUND - (Math.max(0, h) / maxHeight) * (GROUND - TOP)

  const step = (key: string) => r.steps.find((s) => s.key === key)?.value ?? null
  const reachCombined = step('reachCombined') ?? 0
  const combinedSteps = r.steps.filter((s) => COMBINED_STEPS.has(s.key))
  const combined = combinedSteps[combinedSteps.length - 1]?.value ?? null
  const k = r.steps.some((s) => s.key === 'withWalkingSpeed') ? 1600 : 2000
  const timeDistance = r.t === null ? null : k * r.t + (r.supplement ?? 0)
  const s = r.s ?? combined
  const structureGoverns = step('separation')

  // The arrow that sets the result: a structure when it governs, otherwise
  // the longest reach past the field, the reach through it on a tie.
  const fieldPaths = r.paths.filter((p) => p.ok && (p.path === 'over' || p.path === 'through' || p.path === 'under'))
  let governs: ReachPath | null = null
  if (structureGoverns !== null) {
    governs = r.paths.find((p) => p.k === null && p.s === structureGoverns)?.path ?? null
  } else if (fieldPaths.length > 0) {
    const longest = Math.max(...fieldPaths.map((p) => p.reach ?? 0))
    governs = (fieldPaths.find((p) => p.path === 'through' && p.reach === longest) ?? fieldPaths.find((p) => p.reach === longest))?.path ?? null
  }

  const reaches = r.paths.map((p) => p.reach ?? 0)
  const total = s ?? Math.max(1, ...reaches) * 1.3
  const px = (value: number) => ((XR - XC) * Math.max(0, value)) / Math.max(total, 1)

  const fieldTop = y(hdt)
  const fieldBottom = y(e.structureBelow ? Math.max(hdb, gap) : hdb)
  const arrows = r.paths.map((p) => {
    let y0: number
    let shape: 'over' | 'through' | 'under'
    if (p.path === 'over') {
      y0 = fieldTop - 9
      shape = 'over'
    } else if (p.path === 'overStructure') {
      y0 = y(hdt + STRUCTURE_HEIGHT) - 9
      shape = 'over'
    } else if (p.path === 'through') {
      y0 = (fieldTop + fieldBottom) / 2
      shape = 'through'
    } else {
      y0 = Math.min(GROUND - 4, y(p.path === 'underStructure' ? gap : hdb) + 9)
      shape = 'under'
    }
    const len = p.ok ? px(p.reach ?? 0) : 0
    const end = XC + len
    const hook = shape === 'over' ? 16 : shape === 'under' ? -16 : 0
    const d =
      shape === 'through'
        ? `M ${XC - 38} ${y0} L ${end} ${y0}`
        : `M ${XC - 38} ${y0 + hook} Q ${XC - 12} ${y0 - hook / 8} ${XC} ${y0} L ${end} ${y0}`
    const label = p.ok ? `${SYMBOLS[p.path]} = ${mm(p.reach ?? 0)}` : `${SYMBOLS[p.path]}: ${t('tools.safetyDistance.paths.notCovered')}`
    // A label goes after its arrow; one that would run into the hazard zone
    // ends at the arrow tip instead, and one at the reference plane sits
    // above its line.
    const beside = end + 100 < XR
    const onGround = y0 + 4 >= GROUND - 3
    return {
      key: p.path,
      d,
      ok: p.ok,
      governs: p.path === governs,
      label,
      labelX: beside ? end + 5 : end,
      labelY: beside && !onGround ? y0 + 4 : y0 - 5,
      anchor: beside ? 'start' : 'end',
      crossY: y0,
    }
  })

  // S split into the reach, the distance covered during T and whatever a
  // minimum or a supplement adds; a governing structure is S on its own.
  const segments: { key: string; label: string; value: number }[] = []
  if (s !== null) {
    if (structureGoverns !== null && governs) {
      segments.push({ key: 'structure', label: `${SYMBOLS[governs]} = ${mm(s)}`, value: s })
    } else {
      if (reachCombined > 0) segments.push({ key: 'reach', label: `D_DS = ${mm(reachCombined)}`, value: reachCombined })
      if (timeDistance !== null) {
        const symbol = (r.supplement ?? 0) > 0 ? 'K · T + Z' : 'K · T'
        segments.push({ key: 'time', label: `${symbol} = ${mm(timeDistance)}`, value: timeDistance })
        const extra = s - reachCombined - timeDistance
        if (extra > 0.05) segments.push({ key: 'extra', label: `+ ${mm(extra)}`, value: extra })
      }
    }
  }
  let x = XC
  let above = false
  const placed = segments.map((seg) => {
    const width = px(seg.value)
    const start = x
    x += width
    above = width >= 90 ? true : !above
    return { ...seg, start, end: start + width, mid: start + width / 2, labelY: above ? SEG_Y - 6 : SEG_Y + 14 }
  })

  const hazardTop = Math.max(TOP - 6, Math.min(y(hh) - 14, GROUND - 28))
  return {
    y,
    hdt,
    hdb,
    hh,
    fieldTop,
    fieldBottom,
    structureAboveTop: y(hdt + STRUCTURE_HEIGHT),
    structureBelowTop: fieldBottom,
    structureBelowBottom: y(gap),
    hazardTop,
    hazardBottom: hazardTop + 28,
    arrows,
    segments: placed,
    s,
  }
})

/**
 * Placement of a label along a vertical dimension from the reference plane
 * up to `top`: centred on a long dimension, starting at the plane and
 * reading upwards on a short one, so it never runs below the plane.
 */
function heightLabel(x: number, top: number, text: string) {
  const short = GROUND - top < text.length * 6 + 8
  const y = short ? GROUND - 3 : (GROUND + top) / 2
  return { x, y, text, anchor: short ? 'start' : 'middle', transform: `rotate(-90 ${x} ${y})` }
}

function heightText(symbol: string, value: number | null): string {
  return value === null ? symbol : `${symbol} = ${mm(value)}`
}

const labels = computed(() => {
  const d = drawing.value
  return {
    top: heightLabel(26, d.fieldTop, heightText('H_DT', props.inputs.topEdge)),
    bottom: heightLabel(46, d.y(d.hdb), heightText('H_DB', props.inputs.bottomEdge)),
    hazard: heightLabel(436, d.y(d.hh), heightText('H_H', props.inputs.hazardHeight)),
  }
})

// While fields are empty S stands on its own; a configuration the standard
// does not cover says so.
const sLabel = computed(() => {
  const s = props.result.s
  if (s !== null) return `S = ${mm(roundUp(s, 1))}`
  return props.result.messages.some((m) => m.level === 'error') ? `S: ${t(`${P}.labels.noResult`)}` : 'S'
})
</script>

<template>
  <figure class="sk" data-testid="sd-sketch-espe">
    <svg viewBox="0 0 444 262" class="sk-svg" role="img" :aria-label="t(`${P}.captions.espe`)">
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
        <!-- Marker sizes scale with the stroke, so the thick arrow gets a smaller one. -->
        <marker :id="`${id}-arrow-bold`" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="3.2" markerHeight="3.2" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" class="sk-arrowhead" />
        </marker>
      </defs>

      <!-- Reference plane -->
      <rect x="8" :y="GROUND" width="428" height="7" :fill="`url(#${id}-hatch)`" class="sk-none" />
      <line x1="8" x2="436" :y1="GROUND" :y2="GROUND" class="sk-ground" />
      <SafetyDistanceSvgText :text="t(`${P}.labels.referencePlane`)" :x="XC + 10" :y="GROUND + 19" class="sk-label sk-label--muted" />

      <!-- Height dimensions -->
      <line x1="24" :x2="XC - 8" :y1="drawing.fieldTop" :y2="drawing.fieldTop" class="sk-ext" />
      <line x1="30" x2="30" :y1="GROUND" :y2="drawing.fieldTop" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
      <SafetyDistanceSvgText
        :text="labels.top.text"
        :x="labels.top.x"
        :y="labels.top.y"
        :text-anchor="labels.top.anchor"
        :transform="labels.top.transform"
        class="sk-label sk-label--halo"
      />
      <template v-if="drawing.hdb > 0">
        <line x1="44" :x2="XC - 8" :y1="drawing.y(drawing.hdb)" :y2="drawing.y(drawing.hdb)" class="sk-ext" />
        <line x1="50" x2="50" :y1="GROUND" :y2="drawing.y(drawing.hdb)" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
        <SafetyDistanceSvgText
          :text="labels.bottom.text"
          :x="labels.bottom.x"
          :y="labels.bottom.y"
          :text-anchor="labels.bottom.anchor"
          :transform="labels.bottom.transform"
          class="sk-label sk-label--halo"
        />
      </template>

      <!-- Device, field and protective structures -->
      <rect :x="XC - 5" :y="drawing.fieldTop - 8" width="10" :height="GROUND - drawing.fieldTop + 8" class="sk-device" />
      <line :x1="XC" :x2="XC" :y1="drawing.fieldTop" :y2="drawing.fieldBottom" class="sk-field" />
      <rect
        v-if="inputs.structureAbove"
        :x="XC - 7"
        :y="drawing.structureAboveTop"
        width="14"
        :height="drawing.fieldTop - drawing.structureAboveTop"
        :fill="`url(#${id}-hatch)`"
        class="sk-structure"
      />
      <rect
        v-if="inputs.structureBelow"
        :x="XC - 7"
        :y="drawing.structureBelowTop"
        width="14"
        :height="Math.max(0, drawing.structureBelowBottom - drawing.structureBelowTop)"
        :fill="`url(#${id}-hatch)`"
        class="sk-structure"
      />

      <!-- Hazard zone at H_H -->
      <rect :x="XR" :y="drawing.hazardTop" :width="HAZARD_RIGHT - XR" height="28" :fill="`url(#${id}-cross)`" class="sk-hazard" />
      <SafetyDistanceSvgText :text="t(`${P}.labels.hazard`)" :x="(XR + HAZARD_RIGHT) / 2" :y="drawing.hazardTop - 5" text-anchor="middle" class="sk-label" />
      <line :x1="HAZARD_RIGHT" x2="432" :y1="drawing.y(drawing.hh)" :y2="drawing.y(drawing.hh)" class="sk-ext" />
      <line x1="426" x2="426" :y1="GROUND" :y2="drawing.y(drawing.hh)" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
      <SafetyDistanceSvgText
        :text="labels.hazard.text"
        :x="labels.hazard.x"
        :y="labels.hazard.y"
        :text-anchor="labels.hazard.anchor"
        :transform="labels.hazard.transform"
        class="sk-label sk-label--halo"
      />

      <!-- Ways past the field; the thick arrow sets the result -->
      <g
        v-for="arrow in drawing.arrows"
        :key="arrow.key"
        :data-testid="`sd-sketch-path-${arrow.key}`"
        :data-governs="arrow.governs ? 'true' : 'false'"
      >
        <path
          :d="arrow.d"
          :marker-end="arrow.ok ? `url(#${id}-${arrow.governs ? 'arrow-bold' : 'arrow'})` : undefined"
          class="sk-path"
          :class="{ 'sk-path--governs': arrow.governs }"
        />
        <path v-if="!arrow.ok" :d="`M ${XC - 5} ${arrow.crossY - 5} L ${XC + 5} ${arrow.crossY + 5} M ${XC + 5} ${arrow.crossY - 5} L ${XC - 5} ${arrow.crossY + 5}`" class="sk-cross" />
        <SafetyDistanceSvgText
          :text="arrow.label"
          :x="arrow.labelX"
          :y="arrow.labelY"
          :text-anchor="arrow.anchor"
          class="sk-label sk-label--halo"
          :class="{ 'sk-label--strong': arrow.governs }"
        />
      </g>

      <!-- S and its parts -->
      <line :x1="XC" :x2="XC" :y1="SEG_Y - 6" :y2="S_Y + 4" class="sk-ext" />
      <line :x1="XR" :x2="XR" :y1="SEG_Y - 6" :y2="S_Y + 4" class="sk-ext" />
      <g v-for="seg in drawing.segments" :key="seg.key" :data-testid="`sd-sketch-seg-${seg.key}`">
        <line
          :x1="seg.start"
          :x2="seg.end"
          :y1="SEG_Y"
          :y2="SEG_Y"
          :marker-start="`url(#${id}-arrow)`"
          :marker-end="`url(#${id}-arrow)`"
          class="sk-dim"
        />
        <line :x1="seg.end" :x2="seg.end" :y1="SEG_Y - 5" :y2="SEG_Y + 5" class="sk-dim" />
        <SafetyDistanceSvgText :text="seg.label" :x="seg.mid" :y="seg.labelY" text-anchor="middle" class="sk-label sk-label--halo" />
      </g>
      <line :x1="XC" :x2="XR" :y1="S_Y" :y2="S_Y" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
      <SafetyDistanceSvgText
        :text="sLabel"
        :x="(XC + XR) / 2"
        :y="S_Y + 15"
        text-anchor="middle"
        class="sk-label sk-label--strong"
        data-testid="sd-sketch-s"
      />
    </svg>
    <figcaption class="sk-caption">{{ t(`${P}.captions.espe`) }}</figcaption>
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
  fill: none;
  stroke: var(--p-text-muted-color);
  stroke-width: 1;
}

// Dashes suggest the beams of the field, so it reads without colour too.
.sk-field {
  stroke: var(--p-primary-color);
  stroke-width: 4;
  stroke-dasharray: 3 2;
}

.sk-structure {
  stroke: var(--p-text-color);
  stroke-width: 1;
}

.sk-hazard {
  stroke: var(--p-text-color);
  stroke-width: 1.25;
}

.sk-path {
  fill: none;
  stroke: var(--p-text-color);
  stroke-width: 1.25;
  stroke-dasharray: 5 3;

  &--governs {
    stroke-width: 2.75;
    stroke-dasharray: none;
  }
}

.sk-cross {
  stroke: var(--p-text-color);
  stroke-width: 1.5;
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

  // A halo in the card colour keeps a label legible over lines behind it.
  &--halo {
    paint-order: stroke;
    stroke: var(--p-content-background);
    stroke-width: 3px;
    stroke-linejoin: round;
  }
}
</style>
