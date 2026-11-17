<script setup lang="ts">
// One hand-rolled inline SVG per state machine. Layout comes from
// stateMachineLayout; this component turns layers into coordinates and draws.
// Styling uses OpenVue's semantic --p-* tokens so both themes work.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { layoutStateMachine } from '../utils/stateMachineLayout'
import { resolveStateLabel } from '../utils/stateMachineLabels'
import type { StateMachineResponse } from '../types/stateMachinesResponse'

const props = defineProps<{
  machine: StateMachineResponse
}>()

const { t, te } = useI18n()

const NODE_WIDTH = 168
const NODE_HEIGHT = 46
const LAYER_GAP = 96
const NODE_GAP = 22
const MARGIN = 28
// Extra bottom room a back-edge's downward arc needs, on top of the tallest
// layer; only added to the canvas height when a back edge actually exists.
const BACK_EDGE_ROOM = 70

const layout = computed(() => layoutStateMachine(props.machine.states, props.machine.edges))

interface Point {
  x: number
  y: number
}

const nodePositions = computed(() => {
  const positions = new Map<string, Point>()
  const layerHeights = layout.value.layers.map(
    (layer) => layer.length * NODE_HEIGHT + Math.max(0, layer.length - 1) * NODE_GAP,
  )
  const maxHeight = Math.max(0, ...layerHeights)

  layout.value.layers.forEach((layerStates, layerIndex) => {
    const startY = MARGIN + (maxHeight - layerHeights[layerIndex]!) / 2
    layerStates.forEach((value, i) => {
      positions.set(value, {
        x: MARGIN + layerIndex * (NODE_WIDTH + LAYER_GAP),
        y: startY + i * (NODE_HEIGHT + NODE_GAP),
      })
    })
  })

  return positions
})

interface DiagramNode {
  value: string
  label: string
  initial: boolean
  terminal: boolean
  x: number
  y: number
}

const nodes = computed<DiagramNode[]>(() =>
  props.machine.states.map((state) => {
    const pos = nodePositions.value.get(state.value) ?? { x: MARGIN, y: MARGIN }
    return {
      value: state.value,
      label: resolveStateLabel(t, te, props.machine.key, state.value),
      initial: state.initial === true,
      terminal: state.terminal,
      x: pos.x,
      y: pos.y,
    }
  }),
)

function rightAnchor(p: Point): Point {
  return { x: p.x + NODE_WIDTH, y: p.y + NODE_HEIGHT / 2 }
}
function leftAnchor(p: Point): Point {
  return { x: p.x, y: p.y + NODE_HEIGHT / 2 }
}
function bottomAnchor(p: Point): Point {
  return { x: p.x + NODE_WIDTH / 2, y: p.y + NODE_HEIGHT }
}
function topAnchor(p: Point): Point {
  return { x: p.x + NODE_WIDTH / 2, y: p.y }
}

interface DiagramEdge {
  key: string
  kind: 'forward' | 'back' | 'self'
  path: string
}

const edges = computed<DiagramEdge[]>(() => {
  const positions = nodePositions.value
  const layerOf = layout.value.layerOf

  return props.machine.edges.map((edge, index) => {
    const key = `${edge.from_state}->${edge.to_state}-${index}`
    const from = positions.get(edge.from_state)
    const to = positions.get(edge.to_state)
    if (!from || !to) return { key, kind: 'forward', path: '' }

    if (edge.from_state === edge.to_state) {
      // Self-loop: a small arc off the top of the node and back in.
      const top = topAnchor(from)
      const path =
        `M ${top.x - 16} ${top.y} ` +
        `C ${top.x - 30} ${top.y - 34}, ${top.x + 30} ${top.y - 34}, ${top.x + 16} ${top.y}`
      return { key, kind: 'self', path }
    }

    const fromLayer = layerOf[edge.from_state] ?? 0
    const toLayer = layerOf[edge.to_state] ?? 0

    if (toLayer > fromLayer) {
      // Forward edge: a gentle horizontal S-curve, left-to-right.
      const start = rightAnchor(from)
      const end = leftAnchor(to)
      const dx = Math.max(40, (end.x - start.x) / 2)
      const path = `M ${start.x} ${start.y} C ${start.x + dx} ${start.y}, ${end.x - dx} ${end.y}, ${end.x} ${end.y}`
      return { key, kind: 'forward', path }
    }

    // A back edge runs below both nodes in a wide dashed arc, distinct from the
    // forward edges.
    const start = bottomAnchor(from)
    const end = bottomAnchor(to)
    const arc = BACK_EDGE_ROOM - 10 + Math.abs(fromLayer - toLayer) * 14
    const midY = Math.max(start.y, end.y) + arc
    const path = `M ${start.x} ${start.y} C ${start.x} ${midY}, ${end.x} ${midY}, ${end.x} ${end.y}`
    return { key, kind: 'back', path }
  })
})

const hasBackEdge = computed(() => edges.value.some((e) => e.kind === 'back'))

const svgWidth = computed(() => {
  const layerCount = layout.value.layers.length
  if (layerCount === 0) return 0
  return MARGIN * 2 + layerCount * NODE_WIDTH + (layerCount - 1) * LAYER_GAP
})

const svgHeight = computed(() => {
  const layerHeights = layout.value.layers.map(
    (layer) => layer.length * NODE_HEIGHT + Math.max(0, layer.length - 1) * NODE_GAP,
  )
  const tallest = Math.max(0, ...layerHeights, NODE_HEIGHT)
  return MARGIN * 2 + tallest + (hasBackEdge.value ? BACK_EDGE_ROOM : 0)
})

// Unique per machine, since marker ids resolve across the whole document.
const forwardArrowId = computed(() => `sm-arrow-forward-${props.machine.key}`)
const backArrowId = computed(() => `sm-arrow-back-${props.machine.key}`)
</script>

<template>
  <svg
    v-if="nodes.length > 0"
    class="sm-diagram"
    :width="svgWidth"
    :height="svgHeight"
    :viewBox="`0 0 ${svgWidth} ${svgHeight}`"
    role="img"
    :aria-label="machine.entity"
  >
    <defs>
      <marker
        :id="forwardArrowId"
        viewBox="0 0 10 10"
        refX="8.5"
        refY="5"
        markerWidth="7"
        markerHeight="7"
        orient="auto-start-reverse"
      >
        <path d="M0,0 L10,5 L0,10 z" class="sm-arrowhead sm-arrowhead-forward" />
      </marker>
      <marker
        :id="backArrowId"
        viewBox="0 0 10 10"
        refX="8.5"
        refY="5"
        markerWidth="7"
        markerHeight="7"
        orient="auto-start-reverse"
      >
        <path d="M0,0 L10,5 L0,10 z" class="sm-arrowhead sm-arrowhead-back" />
      </marker>
    </defs>

    <g class="sm-edges">
      <path
        v-for="edge in edges"
        :key="edge.key"
        :d="edge.path"
        fill="none"
        class="sm-edge"
        :class="`sm-edge-${edge.kind}`"
        :data-kind="edge.kind"
        :marker-end="`url(#${edge.kind === 'back' || edge.kind === 'self' ? backArrowId : forwardArrowId})`"
      />
    </g>

    <g class="sm-nodes">
      <g
        v-for="node in nodes"
        :key="node.value"
        class="sm-node"
        :class="{ 'sm-node-initial': node.initial, 'sm-node-terminal': node.terminal }"
        :data-state="node.value"
        :data-initial="node.initial"
        :data-terminal="node.terminal"
      >
        <title>{{ node.label }}</title>
        <rect
          :x="node.x"
          :y="node.y"
          :width="NODE_WIDTH"
          :height="NODE_HEIGHT"
          rx="9"
          class="sm-node-rect"
        />
        <!-- Terminal states get a double border, so the distinction survives any
             theme or print. -->
        <rect
          v-if="node.terminal"
          :x="node.x + 4"
          :y="node.y + 4"
          :width="NODE_WIDTH - 8"
          :height="NODE_HEIGHT - 8"
          rx="6"
          class="sm-node-rect-inner"
        />
        <circle
          v-if="node.initial"
          :cx="node.x + 10"
          :cy="node.y + 10"
          r="4.5"
          class="sm-node-initial-badge"
        />
        <text
          :x="node.x + NODE_WIDTH / 2"
          :y="node.y + NODE_HEIGHT / 2"
          text-anchor="middle"
          dominant-baseline="central"
          class="sm-node-label"
        >
          {{ node.label }}
        </text>
      </g>
    </g>
  </svg>
</template>

<style scoped lang="scss">
.sm-diagram {
  display: block;
}

.sm-node-rect {
  fill: var(--p-content-background);
  stroke: var(--p-content-border-color);
  stroke-width: 1.5;
}

.sm-node-rect-inner {
  fill: none;
  stroke: var(--p-text-muted-color);
  stroke-width: 1.25;
}

.sm-node-initial .sm-node-rect {
  stroke: var(--p-primary-color);
  stroke-width: 2.5;
}

.sm-node-initial-badge {
  fill: var(--p-primary-color);
}

.sm-node-label {
  fill: var(--p-text-color);
  font-size: var(--font-size-sm);
  font-weight: 500;
}

.sm-edge {
  stroke: var(--p-text-color);
  stroke-width: 1.5;
}

.sm-edge-back,
.sm-edge-self {
  stroke: var(--p-text-muted-color);
  stroke-dasharray: 6 4;
}

.sm-arrowhead-forward {
  fill: var(--p-text-color);
}

.sm-arrowhead-back {
  fill: var(--p-text-muted-color);
}
</style>
