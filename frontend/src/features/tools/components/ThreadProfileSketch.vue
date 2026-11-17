<script setup lang="ts">
import { useId } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const id = useId()

// Half section through a nut (top, internal thread) on a bolt (bottom,
// external thread), drawn to the ISO basic profile: pitch P = 80 units, so the
// depths and the 60° flanks are true to scale. Diameters are measured from
// the axis at the bottom. The nut stops before the last groove so the flank
// angle can be shown on the bare bolt.
const P = 80
const H = 0.866025 * P
const X0 = 60
const X_END = 360
const NUT_END = 300
const MAJOR = 70
const APEX = MAJOR - H / 8
const PITCH_LINE = MAJOR + (3 / 8) * H
const MINOR_INTERNAL = MAJOR + (5 / 8) * H
const MINOR_EXTERNAL = MAJOR + 0.613435 * P
const NUT_ROOT = MAJOR - 5
const AXIS = 230
const NUT_TOP = 24

// The fundamental triangle wave: apexes over the bolt crests, valleys under
// the bolt roots.
function triangle(x: number): number {
  const u = (((x - (X0 + P / 16)) % P) + P) % P
  return APEX + Math.min(u, P - u) * (H / (P / 2))
}

function profile(from: number, to: number, top: number, bottom: number): [number, number][] {
  const points: [number, number][] = []
  for (let x = from; x <= to; x += 1) points.push([x, Math.min(Math.max(triangle(x), top), bottom)])
  return points
}

const toPath = (points: [number, number][]) => points.map(([x, y]) => `${x},${y.toFixed(2)}`).join(' ')

const boltEdge = profile(X0, X_END, MAJOR, MINOR_EXTERNAL)
const boltPolygon = toPath([...boltEdge, [X_END, AXIS], [X0, AXIS]])
const nutEdge = profile(X0, NUT_END, NUT_ROOT, MINOR_INTERNAL)
const nutPolygon = toPath([[X0, NUT_TOP], [NUT_END, NUT_TOP], ...nutEdge.reverse()])

// The last groove of the bare bolt: its centre and the virtual flank vertex.
const GROOVE_X = X0 + P / 16 + 3.5 * P
const VERTEX_Y = APEX + H
const ARC_R = 34
const arcStart = { x: GROOVE_X - ARC_R * Math.sin(Math.PI / 6), y: VERTEX_Y - ARC_R * Math.cos(Math.PI / 6) }
const arcEnd = { x: GROOVE_X + ARC_R * Math.sin(Math.PI / 6), y: arcStart.y }

const CREST_A = X0 + P / 16
const diameters = [
  { x: 382, y: MAJOR, label: 'd' },
  { x: 400, y: PITCH_LINE, label: 'd2' },
  { x: 418, y: MINOR_INTERNAL, label: 'D1' },
  { x: 436, y: MINOR_EXTERNAL, label: 'd3' },
]
</script>

<template>
  <svg viewBox="0 0 450 250" class="sketch" role="img" :aria-label="t('tools.threads.sketches.profileAria')">
    <defs>
      <pattern :id="`${id}-hatch`" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="6" class="sketch-hatch" />
      </pattern>
      <marker :id="`${id}-arrow`" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" class="sketch-arrowhead" />
      </marker>
    </defs>

    <polygon :points="boltPolygon" class="sketch-bolt" />
    <polygon :points="nutPolygon" :fill="`url(#${id}-hatch)`" class="sketch-nut" />
    <line :x1="X0 - 10" :x2="X_END + 10" :y1="AXIS" :y2="AXIS" class="sketch-axis" />

    <!-- Pitch over one period, from crest to crest. -->
    <line :x1="CREST_A" :x2="CREST_A" y1="6" :y2="NUT_TOP" class="sketch-extension" />
    <line :x1="CREST_A + P" :x2="CREST_A + P" y1="6" :y2="NUT_TOP" class="sketch-extension" />
    <line :x1="CREST_A" :x2="CREST_A + P" y1="12" y2="12" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sketch-dimension" />
    <text :x="CREST_A + P / 2" y="9" text-anchor="middle" class="sketch-label">P</text>

    <!-- Thread depths on the left. -->
    <line x1="14" :x2="X0" :y1="MAJOR" :y2="MAJOR" class="sketch-extension" />
    <line x1="14" :x2="X0" :y1="MINOR_INTERNAL" :y2="MINOR_INTERNAL" class="sketch-extension" />
    <line x1="34" :x2="X0" :y1="MINOR_EXTERNAL" :y2="MINOR_EXTERNAL" class="sketch-extension" />
    <line x1="42" x2="42" :y1="MAJOR" :y2="MINOR_EXTERNAL" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sketch-dimension" />
    <text x="37" :y="(MAJOR + MINOR_EXTERNAL) / 2" :transform="`rotate(-90 37 ${(MAJOR + MINOR_EXTERNAL) / 2})`" text-anchor="middle" class="sketch-label">h3</text>
    <line x1="22" x2="22" :y1="MAJOR" :y2="MINOR_INTERNAL" :marker-start="`url(#${id}-arrow)`" :marker-end="`url(#${id}-arrow)`" class="sketch-dimension" />
    <text x="17" :y="(MAJOR + MINOR_INTERNAL) / 2" :transform="`rotate(-90 17 ${(MAJOR + MINOR_INTERNAL) / 2})`" text-anchor="middle" class="sketch-label">H1</text>

    <!-- Flank angle on the bare groove. -->
    <line :x1="GROOVE_X" :y1="VERTEX_Y" :x2="GROOVE_X - 52 * Math.sin(Math.PI / 6)" :y2="VERTEX_Y - 52 * Math.cos(Math.PI / 6)" class="sketch-extension" />
    <line :x1="GROOVE_X" :y1="VERTEX_Y" :x2="GROOVE_X + 52 * Math.sin(Math.PI / 6)" :y2="VERTEX_Y - 52 * Math.cos(Math.PI / 6)" class="sketch-extension" />
    <path :d="`M ${arcStart.x} ${arcStart.y} A ${ARC_R} ${ARC_R} 0 0 1 ${arcEnd.x} ${arcEnd.y}`" class="sketch-dimension sketch-arc" />
    <text :x="GROOVE_X" :y="arcStart.y - 5" text-anchor="middle" class="sketch-label">60°</text>

    <!-- Diameters, measured from the axis. -->
    <g v-for="dim in diameters" :key="dim.label">
      <line :x1="X_END" :x2="dim.x + 4" :y1="dim.y" :y2="dim.y" class="sketch-extension" />
      <line :x1="dim.x" :x2="dim.x" :y1="AXIS" :y2="dim.y" :marker-end="`url(#${id}-arrow)`" class="sketch-dimension" />
      <text
        :x="dim.x - 4"
        :y="(AXIS + dim.y) / 2"
        :transform="`rotate(-90 ${dim.x - 4} ${(AXIS + dim.y) / 2})`"
        text-anchor="middle"
        class="sketch-label"
      >
        {{ dim.label }}
      </text>
    </g>
  </svg>
</template>

<style scoped lang="scss">
.sketch {
  display: block;
  width: 100%;
  max-width: 450px;
  height: auto;
}

.sketch-hatch {
  stroke: var(--p-blue-500);
  stroke-width: 1;
}

.sketch-nut {
  stroke: var(--p-blue-500);
  stroke-width: 1.25;
}

.sketch-bolt {
  fill: var(--p-orange-500);
  fill-opacity: 0.3;
  stroke: var(--p-orange-500);
  stroke-width: 1.25;
}

.sketch-axis {
  stroke: var(--p-text-muted-color);
  stroke-width: 1;
  stroke-dasharray: 12 3 2 3;
}

.sketch-extension {
  stroke: var(--p-text-muted-color);
  stroke-width: 0.75;
  stroke-dasharray: 3 3;
}

.sketch-dimension {
  stroke: var(--p-text-color);
  stroke-width: 1;
}

.sketch-arc {
  fill: none;
}

.sketch-arrowhead {
  fill: var(--p-text-color);
}

.sketch-label {
  font-size: var(--font-size-md);
  fill: var(--p-text-color);
  paint-order: stroke;
  stroke: var(--p-content-background);
  stroke-width: 3px;
}
</style>
