<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useDeviceRenderings } from '@/features/product-devices'
import EmptyState from '@/shared/components/EmptyState.vue'
import type { SequenceDocument } from '../composables/useSequenceDocument'
import { useSequenceTiming } from '../composables/useSequenceTiming'
import type { SequenceTiming } from '../composables/useSequenceTiming'
import { buildDisplacementDiagram } from '../utils/displacementDiagram'
import type { DiagramRow, DiagramSegment } from '../utils/displacementDiagram'
import { formatDuration } from '../utils/timing'

/**
 * The displacement-step diagram of a sequence: for each device its steps
 * move, where it is from the start state through every step, with motion
 * drawn as a slope across the step that causes it. Values that differ per
 * variant picked in the page's controls bar. With the time axis on, each
 * step's column is as wide as its estimated duration and says it. It
 * follows the steps on screen, so it shows unsaved changes too. Each row
 * starts with the device's current rendering, also for a released revision.
 */
const props = defineProps<{ doc: SequenceDocument; timing?: SequenceTiming }>()

const { t } = useI18n()
const timing = props.timing ?? useSequenceTiming(props.doc)
const names = timing.names

const diagram = computed(() =>
  buildDisplacementDiagram(props.doc.steps.value, names.deviceById.value, timing.variantId.value),
)

const renderingOf = computed(() => new Map(props.doc.devices.value.map((device) => [device.id, device.rendering_file_id])))
const { urlFor } = useDeviceRenderings({
  productId: () => props.doc.sequence.value?.product_id ?? 0,
  fileIds: () => [...renderingOf.value.values()],
})

function imageOf(row: DiagramRow): string | null {
  return urlFor(renderingOf.value.get(row.deviceId) ?? null)
}

// ── Geometry ──────────────────────────────────────────────────────────

// The device column holds the image, the name and the kind; the level
// labels have a column of their own, so a long name never runs into them.
const IMAGE_SIZE = 40
const DEVICE_WIDTH = 300
const LEVEL_LABEL_WIDTH = 180
const LABEL_WIDTH = DEVICE_WIDTH + LEVEL_LABEL_WIDTH
const NAME_X = IMAGE_SIZE + 12
const COLUMN_WIDTH = 110
// On the time axis: the narrowest column, and the width of the average step.
const MIN_COLUMN_WIDTH = 56
const TIMED_COLUMN_WIDTH = 130
const LEVEL_GAP = 28
const ROW_PAD = 18
const FOOTER_LINE = 16
// Average glyph widths of the 12px bold names and the 11px labels.
const NAME_CHAR = 7
const LABEL_CHAR = 6

const timeAxis = computed(() => timing.timeAxis.value)
// The step numbers, and with the time axis their durations below.
const HEADER = computed(() => (timeAxis.value ? 48 : 34))

function rowHeight(row: DiagramRow): number {
  const levels = Math.max(2, row.levels.length) * LEVEL_GAP + ROW_PAD * 2 - LEVEL_GAP
  return Math.max(levels, IMAGE_SIZE + ROW_PAD * 2)
}

/** The text cut to what fits in the width, with an ellipsis. */
function fit(text: string, width: number, charWidth: number): string {
  const max = Math.max(1, Math.floor(width / charWidth))
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

const rowTops = computed(() => {
  const tops: number[] = []
  let y = HEADER.value
  for (const row of diagram.value.rows) {
    tops.push(y)
    y += rowHeight(row)
  }
  return { tops, bottom: y }
})

/** Column 0 is the start state, column i the i-th step. */
function stepDuration(index: number): number | null {
  if (index === 0) return null
  const step = props.doc.steps.value[index - 1]
  return step ? (timing.steps.value.get(step.key)?.ms ?? null) : null
}

const columnWidths = computed(() => {
  const count = diagram.value.columns.length
  if (!timeAxis.value) return Array.from({ length: count }, () => COLUMN_WIDTH)
  const durations = Array.from({ length: count }, (_, i) => stepDuration(i) ?? 0)
  const timed = durations.filter((ms) => ms > 0)
  const average = timed.length ? timed.reduce((a, b) => a + b, 0) / timed.length : 0
  return durations.map((ms, i) =>
    i === 0 || average === 0 ? COLUMN_WIDTH : Math.max(MIN_COLUMN_WIDTH, (ms / average) * TIMED_COLUMN_WIDTH),
  )
})

const columnStarts = computed(() => {
  const starts = [LABEL_WIDTH]
  for (const w of columnWidths.value) starts.push((starts.at(-1) as number) + w)
  return starts
})

function columnWidth(index: number): number {
  return columnWidths.value[index] ?? COLUMN_WIDTH
}

function durationLabel(index: number): string {
  const step = props.doc.steps.value[index - 1]
  const estimate = step ? timing.steps.value.get(step.key) : undefined
  if (!estimate) return ''
  if (!estimate.estimated && estimate.ms === 0) return '?'
  const time = formatDuration(estimate.ms)
  return estimate.estimated ? time : `≥ ${time}`
}

const footerLines = computed(() =>
  Math.max(1, ...diagram.value.columns.map((column) => column.texts.length + column.jumps.length + (column.timeoutMs ? 1 : 0))),
)

const width = computed(() => columnX(diagram.value.columns.length) + 12)
const height = computed(() => rowTops.value.bottom + 12 + footerLines.value * FOOTER_LINE + 8)

function columnX(index: number): number {
  return columnStarts.value[index] ?? LABEL_WIDTH
}

function levelY(rowIndex: number, level: number): number {
  const row = diagram.value.rows[rowIndex]!
  const top = rowTops.value.tops[rowIndex]!
  return top + rowHeight(row) - ROW_PAD - level * LEVEL_GAP
}

/** The line of one device through one column, and whether its start is unknown. */
function segmentPath(rowIndex: number, column: number, segment: DiagramSegment): { points: string; unknown: boolean } | null {
  const to = segment.to ?? segment.from
  if (to === null) return null
  const from = segment.from ?? to
  const x0 = columnX(column)
  const w = columnWidth(column)
  const yf = levelY(rowIndex, from)
  const yt = levelY(rowIndex, to)
  const pts: Array<[number, number]> = (() => {
    switch (segment.shape) {
      case 'hold':
        return [
          [x0, yf],
          [x0 + w, yf],
        ]
      case 'move':
        return [
          [x0, yf],
          [x0 + w * 0.75, yt],
          [x0 + w, yt],
        ]
      case 'continuous':
        return [
          [x0, yf],
          [x0 + w * 0.25, yt],
          [x0 + w * 0.75, yt],
          [x0 + w, yf],
        ]
      case 'pulse':
        return [
          [x0, yf],
          [x0 + w * 0.15, yt],
          [x0 + w * 0.3, yf],
          [x0 + w, yf],
        ]
    }
  })()
  return { points: pts.map(([x, y]) => `${x},${y}`).join(' '), unknown: segment.from === null }
}

function footerTexts(index: number): string[] {
  const column = diagram.value.columns[index]!
  return [
    ...column.jumps.map((jump) => (jump === 'end' ? t('sequences.diagram.end') : jump)),
    ...(column.timeoutMs ? [t('sequences.diagram.timeout', { ms: column.timeoutMs })] : []),
    ...column.texts,
  ]
}
</script>

<template>
  <div class="card diagram-view">
    <EmptyState v-if="diagram.rows.length === 0" :message="t('sequences.diagram.empty')" icon="mdi mdi-chart-timeline" />
    <div v-else class="scroll">
      <svg
        :width="width"
        :height="height"
        :viewBox="`0 0 ${width} ${height}`"
        class="diagram"
        role="img"
        :aria-label="t('sequences.views.diagram')"
        data-testid="sequence-displacement-diagram"
      >
        <!-- Step columns and their numbers -->
        <g class="grid">
          <template v-for="(column, index) in diagram.columns" :key="column.number">
            <line :x1="columnX(index)" :x2="columnX(index)" :y1="HEADER - 6" :y2="rowTops.bottom" />
            <text :x="columnX(index) + columnWidth(index) / 2" :y="timeAxis ? HEADER - 26 : HEADER - 12" class="step-label">
              {{ column.number === 0 ? t('sequences.diagram.start') : column.label }}
            </text>
            <text
              v-if="timeAxis && column.number > 0"
              :x="columnX(index) + columnWidth(index) / 2"
              :y="HEADER - 12"
              class="duration"
              data-testid="sequence-diagram-duration"
            >
              {{ durationLabel(index) }}
            </text>
          </template>
          <line
            :x1="columnX(diagram.columns.length)"
            :x2="columnX(diagram.columns.length)"
            :y1="HEADER - 6"
            :y2="rowTops.bottom"
          />
        </g>

        <!-- One band per device -->
        <g v-for="(row, rowIndex) in diagram.rows" :key="row.deviceId" class="row">
          <line :x1="0" :x2="width" :y1="rowTops.tops[rowIndex]" :y2="rowTops.tops[rowIndex]" class="row-sep" />
          <image
            v-if="imageOf(row)"
            :href="imageOf(row)!"
            :x="0"
            :y="rowTops.tops[rowIndex]! + ROW_PAD"
            :width="IMAGE_SIZE"
            :height="IMAGE_SIZE"
            preserveAspectRatio="xMidYMid meet"
            data-testid="sequence-diagram-image"
          />
          <rect
            v-else
            :x="0.5"
            :y="rowTops.tops[rowIndex]! + ROW_PAD + 0.5"
            :width="IMAGE_SIZE - 1"
            :height="IMAGE_SIZE - 1"
            rx="4"
            class="no-image"
          />
          <text :x="NAME_X" :y="rowTops.tops[rowIndex]! + ROW_PAD + 15" class="device-name">
            <title>{{ row.name }}</title>
            {{ fit(row.name, DEVICE_WIDTH - NAME_X - 12, NAME_CHAR) }}
          </text>
          <text :x="NAME_X" :y="rowTops.tops[rowIndex]! + ROW_PAD + 32" class="device-kind">
            {{
              fit(
                row.drivenBy ? t('sequences.diagram.follows', { name: row.drivenBy }) : row.kind,
                DEVICE_WIDTH - NAME_X - 12,
                LABEL_CHAR,
              )
            }}
          </text>
          <template v-for="(level, levelIndex) in row.levels" :key="level.positionId">
            <line
              :x1="LABEL_WIDTH"
              :x2="columnX(diagram.columns.length)"
              :y1="levelY(rowIndex, levelIndex)"
              :y2="levelY(rowIndex, levelIndex)"
              class="level-line"
            />
            <text :x="LABEL_WIDTH - 8" :y="levelY(rowIndex, levelIndex) + 4" class="level-label">
              <title>{{ level.label }}</title>
              {{ fit(level.label, LEVEL_LABEL_WIDTH - 16, LABEL_CHAR) }}
            </text>
          </template>
          <template v-for="(segment, column) in row.segments" :key="column">
            <polyline
              v-if="segmentPath(rowIndex, column, segment)"
              :points="segmentPath(rowIndex, column, segment)!.points"
              class="motion"
              :class="{ unknown: segmentPath(rowIndex, column, segment)!.unknown, [segment.shape]: true }"
            />
            <text
              v-if="segment.value && segment.to !== null"
              :x="columnX(column) + columnWidth(column) - 2"
              :y="levelY(rowIndex, segment.to) - 4"
              class="value"
            >
              {{ segment.value }}
            </text>
          </template>
        </g>
        <line :x1="0" :x2="width" :y1="rowTops.bottom" :y2="rowTops.bottom" class="row-sep" />

        <!-- What the steps say besides the devices -->
        <g class="footer">
          <template v-for="(_column, index) in diagram.columns" :key="index">
            <text
              v-for="(text, line) in footerTexts(index)"
              :key="line"
              :x="columnX(index) + 4"
              :y="rowTops.bottom + 16 + line * FOOTER_LINE"
              class="footer-text"
            >
              <title>{{ text }}</title>
              {{ fit(text, columnWidth(index) - 8, LABEL_CHAR) }}
            </text>
          </template>
        </g>
      </svg>
    </div>
    <p class="legend">{{ t('sequences.diagram.legend') }}</p>
  </div>
</template>

<style scoped lang="scss">
// The standard content card, with room between the chart and its border;
// the chart scrolls inside it.
.diagram-view {
  gap: var(--space-3);
  padding: var(--space-4) var(--space-4);
}

.scroll {
  overflow: auto;
  flex: 1 1 auto;
  min-height: 0;
}

.legend {
  flex-shrink: 0;
  margin: 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.diagram {
  display: block;
  font-family: inherit;

  .grid line {
    stroke: var(--p-content-border-color);
    stroke-dasharray: 2 3;
  }

  .row-sep {
    stroke: var(--p-content-border-color);
  }

  .level-line {
    stroke: var(--p-surface-200);
  }

  .step-label {
    fill: var(--p-text-color);
    font-size: var(--font-size-sm);
    font-weight: 600;
    text-anchor: middle;
  }

  .duration {
    text-anchor: middle;
  }

  .no-image {
    fill: var(--p-content-hover-background);
    stroke: var(--p-content-border-color);
  }

  .device-name {
    fill: var(--p-text-color);
    font-size: var(--font-size-sm);
    font-weight: 600;
  }

  .device-kind,
  .duration,
  .level-label,
  .footer-text {
    fill: var(--p-text-muted-color);
    font-size: var(--font-size-xs);
  }

  .level-label {
    text-anchor: end;
  }

  .motion {
    fill: none;
    stroke: var(--p-primary-color);
    stroke-width: 2.5;
    stroke-linejoin: round;

    &.hold {
      stroke-width: 2;
    }

    &.continuous,
    &.pulse {
      stroke-dasharray: 5 3;
    }

    &.unknown {
      stroke: var(--p-text-muted-color);
      stroke-dasharray: 1 3;
    }
  }

  .value {
    fill: var(--p-text-color);
    font-size: var(--font-size-xs);
    text-anchor: end;
  }
}
</style>
