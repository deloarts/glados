<script setup lang="ts">
/**
 * Beam heights of a multi-beam device or a single beam above the reference
 * plane, to scale, with the limits a beam arrangement has to keep as dashed
 * lines: the lowest beam against crawling under, the top beam against
 * stepping over. A row of Annex C that matches the entered heights is named.
 * In front of a step the step shows behind the beams, and the lowest beam is
 * limited relative to its upper level.
 */
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { matchBeamRow } from '../utils/safetyDistance/espe'
import { numberOptions } from '../utils/safetyDistance/format'
import type { EspeInputs } from '../utils/safetyDistance/types'
import SafetyDistanceSvgText from './SafetyDistanceSvgText.vue'

const props = defineProps<{ inputs: EspeInputs }>()

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()
const id = useId()

const P = 'tools.safetyDistance.sketch'

const GROUND = 214
const TOP = 34
const EMITTER = 132
const RECEIVER = 286

function num(value: number): string {
  return formatNumber(value, numberOptions(1))
}

const drawing = computed(() => {
  const single = props.inputs.device === 'singleBeam'
  const heights = single ? [200] : [...new Set(props.inputs.beamHeights)].sort((a, b) => a - b)
  const highest = heights[heights.length - 1] ?? 0
  const step = !single && props.inputs.stepArrangement ? props.inputs.stepHeight : null
  const maxHeight = single ? 700 : Math.max(1200, highest + 150, (step ?? 0) + 400)
  const y = (h: number) => GROUND - (h / maxHeight) * (GROUND - TOP)

  const limits = single
    ? [{ key: 'opening', h: 500, label: t(`${P}.labels.openingMax`, { h: num(500) }) }]
    : step !== null
      ? [
          { key: 'stepLowest', h: step + 200, label: t(`${P}.labels.stepLowestMax`, { h: num(step + 200) }) },
          { key: 'top', h: 900, label: t(`${P}.labels.topMin`, { h: num(900) }) },
        ]
      : [
          { key: 'lowest', h: 200, label: t(`${P}.labels.lowestMax`, { h: num(200) }) },
          { key: 'industrial', h: 300, label: t(`${P}.labels.industrialMax`, { h: num(300) }) },
          { key: 'top', h: 900, label: t(`${P}.labels.topMin`, { h: num(900) }) },
        ]

  const widest = step !== null ? 500 : 400
  const beams = heights.map((h) => ({ h, y: y(h), label: num(h) }))
  const spacings = beams.slice(1).map((beam, i) => {
    const below = beams[i] as (typeof beams)[number]
    const gap = beam.h - below.h
    return { key: `${below.h}-${beam.h}`, top: beam.y, bottom: below.y, label: num(gap), wide: gap > widest }
  })

  const match = single || step !== null ? null : matchBeamRow(heights)
  return {
    single,
    beams,
    spacings,
    limits: limits.map((limit) => ({ ...limit, y: y(limit.h) })),
    postTop: y(highest) - 22,
    step: step === null ? null : { y: y(step), label: t(`${P}.labels.step`, { h: num(step) }) },
    match: match ? t(`${P}.labels.annexMatch`, { table: match.table, beams: match.row.beams }) : '',
  }
})
</script>

<template>
  <figure class="sk" data-testid="sd-sketch-beams">
    <svg viewBox="0 0 380 246" class="sk-svg" role="img" :aria-label="t(`${P}.captions.${drawing.single ? 'singleBeam' : 'beams'}`)">
      <defs>
        <pattern :id="`${id}-hatch`" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" class="sk-hatch" />
        </pattern>
        <marker :id="`${id}-arrow`" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" class="sk-arrowhead" />
        </marker>
      </defs>

      <rect x="8" :y="GROUND" width="364" height="7" :fill="`url(#${id}-hatch)`" class="sk-none" />
      <line x1="8" x2="372" :y1="GROUND" :y2="GROUND" class="sk-ground" />
      <SafetyDistanceSvgText :text="t(`${P}.labels.referencePlane`)" x="10" :y="GROUND + 20" class="sk-label sk-label--muted" />

      <SafetyDistanceSvgText v-if="drawing.match" :text="drawing.match" x="10" y="16" class="sk-label sk-label--strong" data-testid="sd-sketch-match" />

      <!-- The step behind the beams -->
      <g v-if="drawing.step" data-testid="sd-sketch-step">
        <rect :x="EMITTER" :y="drawing.step.y" :width="RECEIVER - EMITTER" :height="GROUND - drawing.step.y" :fill="`url(#${id}-hatch)`" class="sk-step" />
        <SafetyDistanceSvgText :text="drawing.step.label" :x="(EMITTER + RECEIVER) / 2" :y="GROUND - 6" text-anchor="middle" class="sk-label sk-label--halo" />
      </g>

      <!-- Sender and receiver with the beams between them -->
      <rect :x="EMITTER - 8" :y="drawing.postTop" width="8" :height="GROUND - drawing.postTop" class="sk-post" />
      <rect :x="RECEIVER" :y="drawing.postTop" width="8" :height="GROUND - drawing.postTop" class="sk-post" />
      <g v-for="beam in drawing.beams" :key="beam.h" data-testid="sd-sketch-beam">
        <line :x1="EMITTER" :x2="RECEIVER" :y1="beam.y" :y2="beam.y" class="sk-beam" />
        <circle :cx="EMITTER" :cy="beam.y" r="2.5" class="sk-beam-end" />
        <circle :cx="RECEIVER" :cy="beam.y" r="2.5" class="sk-beam-end" />
        <SafetyDistanceSvgText :text="`${beam.label} mm`" :x="RECEIVER + 14" :y="beam.y + 4" class="sk-label sk-label--halo" />
      </g>

      <!-- Limits every arrangement has to keep -->
      <g v-for="limit in drawing.limits" :key="limit.key" :data-testid="`sd-sketch-limit-${limit.key}`">
        <line x1="8" x2="372" :y1="limit.y" :y2="limit.y" class="sk-limit" />
        <SafetyDistanceSvgText :text="limit.label" :x="EMITTER + 6" :y="limit.y - 3" class="sk-label sk-label--halo" />
      </g>

      <!-- Spacing between neighbouring beams; more than allowed is set in bold -->
      <g v-for="spacing in drawing.spacings" :key="spacing.key">
        <line
          :x1="EMITTER - 18"
          :x2="EMITTER - 18"
          :y1="spacing.bottom"
          :y2="spacing.top"
          :marker-start="`url(#${id}-arrow)`"
          :marker-end="`url(#${id}-arrow)`"
          class="sk-dim"
        />
        <SafetyDistanceSvgText
          :text="spacing.label"
          :x="EMITTER - 22"
          :y="(spacing.top + spacing.bottom) / 2 + 4"
          text-anchor="end"
          class="sk-label sk-label--halo"
          :class="{ 'sk-label--strong': spacing.wide }"
        />
      </g>
    </svg>
    <figcaption class="sk-caption">{{ t(`${P}.captions.${drawing.single ? 'singleBeam' : 'beams'}`) }}</figcaption>
  </figure>
</template>

<style scoped lang="scss">
.sk {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.sk-step {
  stroke: var(--p-text-muted-color);
  stroke-width: 1;
}

.sk-svg {
  display: block;
  width: 100%;
  max-width: 34rem;
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

.sk-limit {
  stroke: var(--p-text-color);
  stroke-width: 0.9;
  stroke-dasharray: 6 4;
}

.sk-post {
  fill: var(--p-content-background);
  stroke: var(--p-text-color);
  stroke-width: 1;
}

.sk-beam {
  stroke: var(--p-primary-color);
  stroke-width: 2;
}

.sk-beam-end {
  fill: var(--p-text-color);
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
