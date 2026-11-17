<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { safeStorage } from '@/core/utils/safeStorage'

import {
  centreOn as centreView,
  fitView,
  gridLayout,
  scaleLimits,
  toImagePoint,
  zoomAt,
  type Size,
  type View,
} from '../utils/zoomPan'
import DeviceOverviewMarkers, { type OverviewMarker } from './DeviceOverviewMarkers.vue'

export type { OverviewMarker }

/**
 * A zoomable, movable view of the product's overview image with the device
 * markers on it, over a dot grid that moves with the image and can be
 * switched off. The image opens fitted to the view; the mouse wheel zooms
 * around the pointer, dragging moves the image, and the buttons zoom in,
 * out and back to the fitted view. A click that does not move the image
 * places the marker while `placing` is on.
 *
 * A large vector drawing is costly to redraw, so the view is kept cheap to
 * move. Wheel and drag updates are applied at most once per frame, and the
 * image lives on a layer of its own that the browser moves and scales as a
 * snapshot, so a drag never redraws it. After a zoom has rested for a moment
 * the snapshot is redrawn once, sharp at the new zoom. The markers sit in
 * their own unscaled layer and follow the view through CSS variables, so
 * they keep their screen size and are never re-rendered by a zoom or a drag.
 */
const props = defineProps<{
  src: string
  markers: OverviewMarker[]
  placing: boolean
  /** Shows a small card with name, type and rendering at every marker. */
  detailed?: boolean
}>()

const emit = defineEmits<{
  place: [point: { x: number; y: number }]
  'marker-enter': [id: number]
  'marker-leave': [id: number]
}>()

const { t } = useI18n()

const viewport = ref<HTMLDivElement | null>(null)
const image = ref<Size>({ width: 0, height: 0 })
const view = reactive<View>({ scale: 1, x: 0, y: 0 })
const fitScale = ref(1)
// Once the user zooms or moves, a resize no longer refits the image.
let adjusted = false

// An SVG without a size of its own has no natural size in some browsers.
const FALLBACK_SIZE = 1000
const CLICK_TOLERANCE_PX = 4
const WHEEL_SPEED = 0.0015
const BUTTON_FACTOR = 1.5
// How long a zoom must rest before the image is drawn sharp again, long
// enough that the notches of one wheel turn count as one zoom.
const SETTLE_MS = 300
const GRID_STORAGE_KEY = 'glados.productDevices.overviewGrid'

function viewportSize(): Size {
  const rect = viewport.value?.getBoundingClientRect()
  return { width: rect?.width ?? 0, height: rect?.height ?? 0 }
}

// ── Applying the view ─────────────────────────────────────────────────

// A wheel or drag update waits here for the next frame; several events in
// one frame fold into the last of them.
let pending: View | null = null
let frame: number | null = null
// The zoom the image's snapshot was last drawn at, and the brief state that
// redraws it: for one frame the image leaves its layer and is drawn at the
// current zoom, then it gets a fresh layer drawn at that zoom.
let sharpScale = 1
const resharpening = ref(false)
let settleTimer: ReturnType<typeof setTimeout> | null = null

/**
 * The view as it will be drawn next, so a second event in the same frame
 * builds on the first.
 */
function current(): View {
  return pending ?? view
}

function commit(next: View): void {
  view.scale = next.scale
  view.x = next.x
  view.y = next.y
  if (settleTimer !== null) clearTimeout(settleTimer)
  settleTimer = null
  if (next.scale !== sharpScale) settleTimer = setTimeout(resharpen, SETTLE_MS)
}

function resharpen(): void {
  settleTimer = null
  sharpScale = view.scale
  resharpening.value = true
  requestAnimationFrame(() =>
    requestAnimationFrame(() => {
      resharpening.value = false
    }),
  )
}

/** Applies a view at once, for the buttons, fitting and centring. */
function apply(next: View): void {
  if (frame !== null) cancelAnimationFrame(frame)
  frame = null
  pending = null
  commit(next)
}

/** Applies a view on the next frame, for the wheel and dragging. */
function schedule(next: View): void {
  pending = next
  if (frame !== null) return
  frame = requestAnimationFrame(() => {
    frame = null
    if (pending) commit(pending)
    pending = null
  })
}

function fit(): void {
  const fitted = fitView(image.value, viewportSize())
  fitScale.value = fitted.scale
  apply(fitted)
  adjusted = false
}

function onImageLoad(event: Event): void {
  const img = event.target as HTMLImageElement
  image.value = {
    width: img.naturalWidth || FALLBACK_SIZE,
    height: img.naturalHeight || FALLBACK_SIZE,
  }
  fit()
}

function zoomed(factor: number, px?: number, py?: number): View {
  const size = viewportSize()
  adjusted = true
  return zoomAt(
    current(),
    factor,
    px ?? size.width / 2,
    py ?? size.height / 2,
    scaleLimits(fitScale.value),
  )
}

function zoomBy(factor: number): void {
  apply(zoomed(factor))
}

function onWheel(event: WheelEvent): void {
  const rect = viewport.value?.getBoundingClientRect()
  if (!rect) return
  schedule(
    zoomed(Math.exp(-event.deltaY * WHEEL_SPEED), event.clientX - rect.left, event.clientY - rect.top),
  )
}

// ── Dragging and clicking ─────────────────────────────────────────────

const drag = ref<{ startX: number; startY: number; viewX: number; viewY: number; moved: boolean } | null>(null)

function onPointerDown(event: PointerEvent): void {
  if (event.button !== 0) return
  ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
  const start = current()
  drag.value = {
    startX: event.clientX,
    startY: event.clientY,
    viewX: start.x,
    viewY: start.y,
    moved: false,
  }
}

function onPointerMove(event: PointerEvent): void {
  const active = drag.value
  if (!active) return
  const dx = event.clientX - active.startX
  const dy = event.clientY - active.startY
  if (!active.moved && Math.hypot(dx, dy) < CLICK_TOLERANCE_PX) return
  active.moved = true
  schedule({ scale: current().scale, x: active.viewX + dx, y: active.viewY + dy })
  adjusted = true
}

function onPointerUp(event: PointerEvent): void {
  const active = drag.value
  drag.value = null
  if (!active || active.moved || !props.placing) return
  const rect = viewport.value?.getBoundingClientRect()
  if (!rect) return
  const point = toImagePoint(current(), image.value, event.clientX - rect.left, event.clientY - rect.top)
  if (point) {
    emit('place', { x: Math.round(point.x * 10000) / 10000, y: Math.round(point.y * 10000) / 10000 })
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === '+' || event.key === '=') zoomBy(BUTTON_FACTOR)
  else if (event.key === '-') zoomBy(1 / BUTTON_FACTOR)
  else if (event.key === '0') fit()
  else return
  event.preventDefault()
}

// ── Dot grid ──────────────────────────────────────────────────────────

function readStoredGrid(): boolean {
  return safeStorage.get(GRID_STORAGE_KEY) !== 'false'
}

// The grid is on unless switched off, and the choice is kept per browser.
const showGrid = ref(readStoredGrid())

function toggleGrid(): void {
  showGrid.value = !showGrid.value
  // Without storage the choice lasts until the page is left.
  safeStorage.set(GRID_STORAGE_KEY, String(showGrid.value))
}

const gridStyle = computed(() => {
  const grid = gridLayout(view, fitScale.value)
  return {
    '--grid-step': `${grid.step}px`,
    transform: `translate(${grid.x}px, ${grid.y}px)`,
  }
})

// ── Layout ────────────────────────────────────────────────────────────

let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  if (typeof ResizeObserver === 'undefined' || !viewport.value) return
  resizeObserver = new ResizeObserver(() => {
    if (!adjusted && image.value.width > 0) fit()
  })
  resizeObserver.observe(viewport.value)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  if (frame !== null) cancelAnimationFrame(frame)
  if (settleTimer !== null) clearTimeout(settleTimer)
})

watch(
  () => props.src,
  () => {
    adjusted = false
  },
)

const stageStyle = computed(() => ({
  width: `${image.value.width}px`,
  height: `${image.value.height}px`,
  transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
}))

// Read by every marker to find its spot on screen.
const markerLayerStyle = computed(() => ({
  '--view-x': `${view.x}px`,
  '--view-y': `${view.y}px`,
  '--view-width': `${image.value.width * view.scale}px`,
  '--view-height': `${image.value.height * view.scale}px`,
}))

const zoomPercent = computed(() => Math.round(view.scale * 100))

/**
 * Moves the view so the marker at (`x`, `y`) sits in the middle, zooming in
 * to at least four times the fitted size.
 */
function centreOn(x: number, y: number): void {
  const scale = Math.max(view.scale, Math.min(fitScale.value * 4, scaleLimits(fitScale.value).max))
  apply(centreView(image.value, viewportSize(), x, y, scale))
  adjusted = true
}

defineExpose({ centreOn, fit })

// The template root is a single element, so a disable comment in front
// of it would turn the root into a fragment and stop attribute fallthrough.
/* eslint-disable vuejs-accessibility/no-static-element-interactions -- a pan and zoom surface with its own keyboard handling, no ARIA widget role fits it */
</script>

<template>
  <div
    ref="viewport"
    class="overview-viewport"
    :class="{ placing, dragging: drag?.moved }"
    tabindex="0"
    :aria-label="t('productDevices.devices.overview.alt')"
    data-testid="device-overview-image"
    @wheel.prevent="onWheel"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="drag = null"
    @keydown="onKeydown"
  >
    <div v-if="showGrid" class="overview-grid" :style="gridStyle" data-testid="device-overview-grid" />
    <div class="overview-stage" :class="{ resharpening }" :style="stageStyle">
      <img
        :src="src"
        :alt="t('productDevices.devices.overview.alt')"
        draggable="false"
        @load="onImageLoad"
      />
    </div>
    <div class="overview-markers" :style="markerLayerStyle">
      <DeviceOverviewMarkers
        :markers="markers"
        :detailed="detailed"
        @marker-enter="emit('marker-enter', $event)"
        @marker-leave="emit('marker-leave', $event)"
      />
    </div>

    <div class="zoom-controls" @pointerdown.stop @pointerup.stop>
      <Button
        icon="mdi mdi-dots-grid"
        size="small"
        severity="secondary"
        :text="!showGrid"
        :aria-pressed="showGrid"
        :aria-label="t('productDevices.devices.overview.grid')"
        v-tooltip.bottom="t('productDevices.devices.overview.grid')"
        data-testid="device-overview-grid-toggle"
        @click="toggleGrid"
      />
      <span class="zoom-separator" aria-hidden="true" />
      <Button
        icon="mdi mdi-magnify-minus-outline"
        size="small"
        severity="secondary"
        text
        :aria-label="t('productDevices.devices.overview.zoomOut')"
        v-tooltip.bottom="t('productDevices.devices.overview.zoomOut')"
        @click="zoomBy(1 / BUTTON_FACTOR)"
      />
      <span class="zoom-percent" data-testid="device-overview-zoom">{{ zoomPercent }} %</span>
      <Button
        icon="mdi mdi-magnify-plus-outline"
        size="small"
        severity="secondary"
        text
        :aria-label="t('productDevices.devices.overview.zoomIn')"
        v-tooltip.bottom="t('productDevices.devices.overview.zoomIn')"
        @click="zoomBy(BUTTON_FACTOR)"
      />
      <Button
        icon="mdi mdi-fit-to-screen-outline"
        size="small"
        severity="secondary"
        text
        :aria-label="t('productDevices.devices.overview.fit')"
        v-tooltip.bottom="t('productDevices.devices.overview.fit')"
        @click="fit"
      />
    </div>
    <div class="usage-hint">{{ t('productDevices.devices.overview.hint') }}</div>
  </div>
</template>

<style scoped lang="scss">
.overview-viewport {
  position: relative;
  flex: 1;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
  background: var(--p-content-hover-background);
  cursor: grab;
  touch-action: none;
  user-select: none;
  outline: none;

  &:focus-visible {
    box-shadow: 0 0 0 2px var(--p-primary-color);
  }

  &.placing {
    cursor: crosshair;
  }

  &.dragging {
    cursor: grabbing;
  }
}

.overview-stage {
  position: absolute;
  top: 0;
  left: 0;
  transform-origin: 0 0;

  // No background of its own, so a transparent drawing shows the canvas
  // behind it.
  img {
    display: block;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }

  // The image keeps a layer of its own, which the browser moves and scales
  // as a snapshot instead of redrawing the drawing every frame.
  will-change: transform;

  &.resharpening {
    will-change: auto;
  }
}

// The dot grid starts one spacing before the viewport and is shifted by
// less than one spacing, so it always covers the viewport.
.overview-grid {
  position: absolute;
  left: calc(-1 * var(--grid-step));
  top: calc(-1 * var(--grid-step));
  width: calc(100% + 2 * var(--grid-step));
  height: calc(100% + 2 * var(--grid-step));
  pointer-events: none;
  background-image: radial-gradient(
    circle,
    color-mix(in srgb, var(--p-text-muted-color) 55%, transparent) 0.6px,
    transparent 1px
  );
  background-size: var(--grid-step) var(--grid-step);
  background-position: calc(var(--grid-step) / 2) calc(var(--grid-step) / 2);
  will-change: transform;
}

// The markers keep their screen size at every zoom, so their layer is not
// scaled; each marker places itself from the view variables set here.
.overview-markers {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.zoom-controls {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-1);
  border-radius: var(--p-border-radius-md);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  cursor: default;
}

.zoom-separator {
  width: 1px;
  align-self: stretch;
  margin: var(--space-1) var(--space-1);
  background: var(--p-content-border-color);
}

.zoom-percent {
  min-width: 3.5rem;
  text-align: center;
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
}

.usage-hint {
  position: absolute;
  left: 0.5rem;
  bottom: 0.5rem;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--p-border-radius-sm);
  background: var(--p-content-background);
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
  pointer-events: none;
}
</style>
