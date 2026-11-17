import { computed, onBeforeUnmount, ref } from 'vue'

import { safeStorage } from '@/core/utils/safeStorage'

/**
 * Drag-to-resize state for a side panel's width, shared by every panel that
 * lets the user drag one edge to resize it. A mousedown on the caller's own
 * drag-handle element starts the drag; width updates live on mousemove and
 * stays clamped to [min, max] throughout, not just at drop.
 *
 * `dockedTo` says which side of the content the panel sits on, matching
 * `PageLayout`'s slot names: 'start' (the default) is a panel rendered into
 * `#panels`, ahead of the content card, whose handle sits on the panel's
 * own trailing edge, dragging right grows it. 'end' is a panel rendered
 * into `#panels-end`, after the content card, whose handle sits on the
 * panel's own leading edge, dragging left grows it.
 *
 * `storageKey`, when given, persists the width to localStorage (best
 * effort, through safeStorage, since a private window or blocked site data
 * can make either throw) so it survives a reload.
 *
 * The handle also works by keyboard (`onResizeKey`, wired by
 * `PanelResizeHandle`): the arrow keys move the edge the way they point,
 * by a small step or a large one with Shift, and Home and End jump to the
 * narrowest and widest the panel may be.
 */
export function useResizablePanelWidth(options: {
  defaultWidth: number
  min?: number
  max?: number | (() => number)
  dockedTo?: 'start' | 'end'
  storageKey?: string
}) {
  const min = options.min ?? 220
  const sign = options.dockedTo === 'end' ? -1 : 1

  function resolveMax(): number {
    if (options.max === undefined) return Number.POSITIVE_INFINITY
    return typeof options.max === 'function' ? options.max() : options.max
  }

  function clamp(value: number): number {
    return Math.min(resolveMax(), Math.max(min, value))
  }

  function readStoredWidth(): number | null {
    if (!options.storageKey) return null
    const raw = safeStorage.get(options.storageKey)
    if (raw === null) return null
    const parsed = Number(raw)
    return Number.isFinite(parsed) ? parsed : null
  }

  function persistWidth(value: number): void {
    if (options.storageKey) safeStorage.set(options.storageKey, String(value))
  }

  const width = ref(clamp(readStoredWidth() ?? options.defaultWidth))
  const isResizing = ref(false)

  let dragStartX = 0
  let dragStartWidth = 0

  function onResizeMove(event: MouseEvent): void {
    width.value = clamp(dragStartWidth + sign * (event.clientX - dragStartX))
  }

  function onResizeEnd(): void {
    isResizing.value = false
    window.removeEventListener('mousemove', onResizeMove)
    window.removeEventListener('mouseup', onResizeEnd)
    persistWidth(width.value)
  }

  function onResizeStart(event: MouseEvent): void {
    isResizing.value = true
    dragStartX = event.clientX
    dragStartWidth = width.value
    window.addEventListener('mousemove', onResizeMove)
    window.addEventListener('mouseup', onResizeEnd)
  }

  function onResizeKey(event: KeyboardEvent): void {
    const step = event.shiftKey ? 64 : 16
    let next: number
    if (event.key === 'ArrowRight') next = width.value + sign * step
    else if (event.key === 'ArrowLeft') next = width.value - sign * step
    else if (event.key === 'Home') next = min
    else if (event.key === 'End' && Number.isFinite(resolveMax())) next = resolveMax()
    else return
    event.preventDefault()
    width.value = clamp(next)
    persistWidth(width.value)
  }

  // The limits the handle reports to assistive technology. An unbounded
  // panel has no maximum to report.
  const max = computed(() => (Number.isFinite(resolveMax()) ? resolveMax() : undefined))

  onBeforeUnmount(() => {
    window.removeEventListener('mousemove', onResizeMove)
    window.removeEventListener('mouseup', onResizeEnd)
  })

  return { width, isResizing, min, max, onResizeStart, onResizeKey }
}
