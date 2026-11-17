<script setup lang="ts">
/**
 * The components of T after equation (3) one after another, from the trigger
 * of the safety function to the intended risk reduction, each as long as its
 * share of T. The parts of the safety control, of the machine and the
 * tolerance are told apart by their fill, so the bar also reads in black and
 * white.
 */
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { numberOptions } from '../utils/safetyDistance/format'
import { RESPONSE_TIME_COMPONENTS } from '../utils/safetyDistance/types'
import type { ResponseTimeComponent, ResponseTimeInputs } from '../utils/safetyDistance/types'
import SafetyDistanceSvgText from './SafetyDistanceSvgText.vue'

const props = defineProps<{ inputs: ResponseTimeInputs }>()

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()
const id = useId()

const P = 'tools.safetyDistance.sketch'

const LEFT = 20
const RIGHT = 424
const BAR_Y = 52
const BAR_HEIGHT = 20
/** Narrower segments carry their symbol below the bar instead of inside it. */
const LABEL_WIDTH = 30

const SYMBOLS: Record<ResponseTimeComponent, string> = {
  tI: 't_I',
  tL: 't_L',
  tO: 't_O',
  tD: 't_D',
  tR: 't_R',
  tM: 't_M',
  tF: 't_F',
  tS: 't_S',
}

type Group = 'control' | 'machine' | 'tolerance'

function groupOf(component: ResponseTimeComponent): Group {
  if (component === 'tI' || component === 'tL' || component === 'tO') return 'control'
  return component === 'tF' || component === 'tS' ? 'tolerance' : 'machine'
}

function seconds(value: number): string {
  return `${formatNumber(value, numberOptions(4))} s`
}

const drawing = computed(() => {
  const values = RESPONSE_TIME_COMPONENTS.map((component) => ({ component, value: props.inputs[component] ?? 0 }))
  const total = values.reduce((sum, v) => sum + v.value, 0)
  const scale = total > 0 ? (RIGHT - LEFT) / total : 0
  let x = LEFT
  let below = 0
  const segments = values
    .filter((v) => v.value > 0)
    .map((v) => {
      const width = v.value * scale
      const start = x
      x += width
      const inside = width >= LABEL_WIDTH
      if (!inside) below += 1
      return {
        key: v.component,
        group: groupOf(v.component),
        start,
        width,
        symbol: SYMBOLS[v.component],
        inside,
        labelY: inside ? BAR_Y + 14 : BAR_Y + BAR_HEIGHT + 12 + ((below + 1) % 2) * 11,
      }
    })

  // Brackets over the safety control and the machine, where they take time.
  const brackets = (['control', 'machine'] as const).flatMap((group) => {
    const parts = segments.filter((s) => s.group === group)
    const first = parts[0]
    const last = parts[parts.length - 1]
    if (!first || !last) return []
    const sum = values.filter((v) => groupOf(v.component) === group).reduce((acc, v) => acc + v.value, 0)
    const symbol = group === 'control' ? 't_SRP/CS' : 't_ME'
    return [{ key: group, start: first.start, end: last.start + last.width, label: `${symbol} = ${seconds(sum)}` }]
  })

  return { total, segments, brackets }
})
</script>

<template>
  <figure v-if="drawing.total > 0" class="sk" data-testid="sd-sketch-timeline">
    <svg viewBox="0 0 444 132" class="sk-svg" role="img" :aria-label="t(`${P}.captions.timeline`)">
      <defs>
        <pattern :id="`${id}-hatch`" patternUnits="userSpaceOnUse" width="5" height="5" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="5" class="sk-hatch" />
        </pattern>
        <pattern :id="`${id}-dots`" patternUnits="userSpaceOnUse" width="5" height="5">
          <circle cx="2.5" cy="2.5" r="1" class="sk-dot" />
        </pattern>
        <marker :id="`${id}-arrow`" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" class="sk-arrowhead" />
        </marker>
      </defs>

      <SafetyDistanceSvgText :text="t(`${P}.labels.trigger`)" :x="LEFT" y="12" class="sk-label sk-label--muted" />
      <SafetyDistanceSvgText :text="t(`${P}.labels.reached`)" :x="RIGHT" y="12" text-anchor="end" class="sk-label sk-label--muted" />

      <g v-for="bracket in drawing.brackets" :key="bracket.key">
        <path :d="`M ${bracket.start + 1} ${BAR_Y - 4} V ${BAR_Y - 10} H ${bracket.end - 1} V ${BAR_Y - 4}`" class="sk-bracket" />
        <SafetyDistanceSvgText :text="bracket.label" :x="(bracket.start + bracket.end) / 2" :y="BAR_Y - 14" text-anchor="middle" class="sk-label sk-label--halo" />
      </g>

      <g v-for="seg in drawing.segments" :key="seg.key" :data-testid="`sd-sketch-time-${seg.key}`">
        <rect
          :x="seg.start"
          :y="BAR_Y"
          :width="seg.width"
          :height="BAR_HEIGHT"
          :fill="seg.group === 'machine' ? `url(#${id}-hatch)` : seg.group === 'tolerance' ? `url(#${id}-dots)` : undefined"
          class="sk-segment"
          :class="`sk-segment--${seg.group}`"
        />
        <line
          v-if="!seg.inside"
          :x1="seg.start + seg.width / 2"
          :x2="seg.start + seg.width / 2"
          :y1="BAR_Y + BAR_HEIGHT"
          :y2="seg.labelY - 9"
          class="sk-leader"
        />
        <SafetyDistanceSvgText :text="seg.symbol" :x="seg.start + seg.width / 2" :y="seg.labelY" text-anchor="middle" class="sk-label sk-label--halo" />
      </g>

      <line :x1="LEFT" :x2="RIGHT" y1="108" y2="108" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
      <SafetyDistanceSvgText
        :text="`T = ${seconds(drawing.total)}`"
        :x="(LEFT + RIGHT) / 2"
        y="124"
        text-anchor="middle"
        class="sk-label sk-label--strong"
        data-testid="sd-sketch-time-total"
      />
    </svg>
    <figcaption class="sk-caption">{{ t(`${P}.captions.timeline`) }}</figcaption>
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
  stroke: var(--p-text-color);
  stroke-width: 1;
}

.sk-dot {
  fill: var(--p-text-color);
}

.sk-segment {
  stroke: var(--p-text-color);
  stroke-width: 1;

  &--control {
    fill: var(--p-primary-color);
    fill-opacity: 0.3;
  }
}

.sk-bracket,
.sk-leader {
  fill: none;
  stroke: var(--p-text-color);
  stroke-width: 0.9;
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
