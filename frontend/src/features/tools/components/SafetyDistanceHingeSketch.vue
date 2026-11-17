<script setup lang="ts">
/**
 * Plan view of a hinged guard with a cam operated switch at the moment the
 * switch trips: the leaf of width G_W and thickness G_T turned by ω about its
 * hinge, the gap b between the far frame edge and the leaf, and the opening
 * e = b − G_T. The angle is drawn larger than it is, since the usual few
 * degrees would leave no room for the dimensions; the labels carry the values.
 */
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { numberOptions } from '../utils/safetyDistance/format'
import type { GuardInputs, SafetyDistanceResult } from '../utils/safetyDistance/types'
import SafetyDistanceSvgText from './SafetyDistanceSvgText.vue'

const props = defineProps<{ inputs: GuardInputs; result: SafetyDistanceResult }>()

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()
const id = useId()

const P = 'tools.safetyDistance.sketch'

const FRAME_Y = 72
const EDGE_X = 112
const HINGE_X = 352
const LENGTH = HINGE_X - EDGE_X
const DRAWN_ANGLE = (22 * Math.PI) / 180
const THICKNESS = 9

function fmt(value: number | null | undefined, unit: string, digits = 1): string {
  if (value === null || value === undefined) return ''
  // Degrees follow the number without a space, millimetres after one.
  return ` = ${formatNumber(value, numberOptions(digits))}${unit === '°' ? '' : ' '}${unit}`
}

const drawing = computed(() => {
  const g = props.inputs
  const step = (key: string) => props.result.steps.find((s) => s.key === key)?.value
  const cos = Math.cos(DRAWN_ANGLE)
  const sin = Math.sin(DRAWN_ANGLE)
  // Along the opened leaf away from the hinge, and across it towards the
  // far frame edge.
  const along = { x: -cos, y: sin }
  const across = { x: -sin, y: -cos }
  const hinge = { x: HINGE_X, y: FRAME_Y }
  const edge = { x: EDGE_X, y: FRAME_Y }
  const at = (base: { x: number; y: number }, a: number, c: number) => ({
    x: base.x + along.x * a + across.x * c,
    y: base.y + along.y * a + across.y * c,
  })

  const tip = at(hinge, LENGTH, 0)
  const leaf = [hinge, tip, at(tip, 0, THICKNESS), at(hinge, 0, THICKNESS)]
  const gapPx = LENGTH * sin
  // b and e both start on the line through the frame edge parallel to the
  // leaf; b ends on the leaf's outer face, e on its inner face.
  const bStart = at(edge, -22, 0)
  const bEnd = at(bStart, 0, -gapPx)
  const eEnd = at(edge, 0, -(gapPx - THICKNESS))
  const arcRadius = 64
  const arcEnd = at(hinge, arcRadius, 0)
  const half = DRAWN_ANGLE / 2

  return {
    leaf: leaf.map((p) => `${p.x},${p.y}`).join(' '),
    tip,
    parallel: { from: at(edge, -40, 0), to: at(edge, 46, 0) },
    b: { from: bStart, to: bEnd, label: at(bStart, -4, -gapPx / 2) },
    e: { from: edge, to: eEnd, label: at(edge, 8, -(gapPx - THICKNESS) / 2) },
    arc: `M ${HINGE_X - arcRadius} ${FRAME_Y} A ${arcRadius} ${arcRadius} 0 0 0 ${arcEnd.x} ${arcEnd.y}`,
    angleLabel: { x: HINGE_X - (arcRadius + 12) * Math.cos(half), y: FRAME_Y + (arcRadius + 12) * Math.sin(half) + 4 },
    thicknessLabel: at(tip, -26, -14),
    labels: {
      width: `G_W${fmt(g.guardWidth, 'mm')}`,
      angle: `ω${fmt(g.angle, '°', 2)}`,
      thickness: `G_T${fmt(g.guardThickness, 'mm')}`,
      b: `b${fmt(step('hingeGap'), 'mm')}`,
      e: `e${fmt(step('opening'), 'mm')}`,
    },
  }
})
</script>

<template>
  <figure class="sk" data-testid="sd-sketch-hinge">
    <svg viewBox="0 0 400 196" class="sk-svg" role="img" :aria-label="t(`${P}.captions.hinge`)">
      <defs>
        <pattern :id="`${id}-hatch`" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" class="sk-hatch" />
        </pattern>
        <marker :id="`${id}-arrow`" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" class="sk-arrowhead" />
        </marker>
      </defs>

      <!-- Fence on both sides and the frame posts -->
      <rect x="8" :y="FRAME_Y - 5" :width="EDGE_X - 18" height="10" :fill="`url(#${id}-hatch)`" class="sk-fence" />
      <rect :x="EDGE_X - 10" :y="FRAME_Y - 7" width="10" height="14" class="sk-post" />
      <rect :x="HINGE_X + 6" :y="FRAME_Y - 5" :width="392 - HINGE_X - 6" height="10" :fill="`url(#${id}-hatch)`" class="sk-fence" />
      <SafetyDistanceSvgText :text="t(`${P}.labels.frame`)" :x="EDGE_X - 10" :y="FRAME_Y - 12" text-anchor="middle" class="sk-label sk-label--muted" />

      <!-- Closed position and the width G_W -->
      <line :x1="EDGE_X" :x2="HINGE_X" :y1="FRAME_Y" :y2="FRAME_Y" class="sk-closed" />
      <line :x1="EDGE_X" :x2="EDGE_X" :y1="FRAME_Y - 14" y2="26" class="sk-ext" />
      <line :x1="HINGE_X" :x2="HINGE_X" :y1="FRAME_Y - 10" y2="26" class="sk-ext" />
      <line :x1="EDGE_X" :x2="HINGE_X" y1="32" y2="32" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sk-dim" />
      <SafetyDistanceSvgText :text="drawing.labels.width" :x="(EDGE_X + HINGE_X) / 2" y="26" text-anchor="middle" class="sk-label sk-label--halo" />

      <!-- Opened leaf, hinge and the angle ω -->
      <polygon :points="drawing.leaf" class="sk-leaf" />
      <circle :cx="HINGE_X" :cy="FRAME_Y" r="4.5" class="sk-hinge" />
      <SafetyDistanceSvgText :text="t(`${P}.labels.hinge`)" :x="HINGE_X + 4" :y="FRAME_Y + 22" class="sk-label sk-label--muted" />
      <path :d="drawing.arc" class="sk-dim sk-arc" />
      <SafetyDistanceSvgText :text="drawing.labels.angle" :x="drawing.angleLabel.x" :y="drawing.angleLabel.y" text-anchor="end" class="sk-label sk-label--halo" />
      <SafetyDistanceSvgText
        :text="drawing.labels.thickness"
        :x="drawing.thicknessLabel.x"
        :y="drawing.thicknessLabel.y + 4"
        text-anchor="start"
        class="sk-label sk-label--halo"
      />

      <!-- b to the outer face of the leaf, e to its inner face -->
      <line :x1="drawing.parallel.from.x" :y1="drawing.parallel.from.y" :x2="drawing.parallel.to.x" :y2="drawing.parallel.to.y" class="sk-ext" />
      <line
        :x1="drawing.b.from.x"
        :y1="drawing.b.from.y"
        :x2="drawing.b.to.x"
        :y2="drawing.b.to.y"
        :marker-start="`url(#${id}-arrow)`"
        :marker-end="`url(#${id}-arrow)`"
        class="sk-dim"
      />
      <SafetyDistanceSvgText :text="drawing.labels.b" :x="drawing.b.label.x + 6" :y="drawing.b.label.y" class="sk-label sk-label--halo" data-testid="sd-sketch-hinge-b" />
      <line
        :x1="drawing.e.from.x"
        :y1="drawing.e.from.y"
        :x2="drawing.e.to.x"
        :y2="drawing.e.to.y"
        :marker-start="`url(#${id}-arrow)`"
        :marker-end="`url(#${id}-arrow)`"
        class="sk-dim sk-dim--strong"
      />
      <SafetyDistanceSvgText
        :text="drawing.labels.e"
        :x="drawing.e.label.x - 6"
        :y="drawing.e.label.y + 4"
        text-anchor="end"
        class="sk-label sk-label--halo sk-label--strong"
        data-testid="sd-sketch-hinge-e"
      />
    </svg>
    <figcaption class="sk-caption">{{ t(`${P}.captions.hinge`) }}</figcaption>
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
  max-width: 36rem;
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

.sk-fence {
  stroke: var(--p-text-color);
  stroke-width: 1;
}

.sk-post {
  fill: var(--p-text-color);
}

.sk-closed {
  stroke: var(--p-text-muted-color);
  stroke-width: 1;
  stroke-dasharray: 10 3 2 3;
}

.sk-leaf {
  fill: var(--p-primary-color);
  fill-opacity: 0.2;
  stroke: var(--p-text-color);
  stroke-width: 1.5;
}

.sk-hinge {
  fill: var(--p-content-background);
  stroke: var(--p-text-color);
  stroke-width: 1.5;
}

.sk-arc {
  fill: none;
}

.sk-dim {
  stroke: var(--p-text-color);
  stroke-width: 1;

  &--strong {
    stroke-width: 1.75;
  }
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
