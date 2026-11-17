import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'

import { useResizablePanelWidth } from '../useResizablePanelWidth'

// useResizablePanelWidth calls onBeforeUnmount(), which needs a real
// component instance (not just an active effect scope) to attach to, the same
// technique as useServerTable.spec.ts.
function mountPanel(...args: Parameters<typeof useResizablePanelWidth>) {
  let panel!: ReturnType<typeof useResizablePanelWidth>
  const wrapper = mount(
    defineComponent({
      setup() {
        panel = useResizablePanelWidth(...args)
        return () => h('div')
      },
    }),
  )
  return { panel, wrapper }
}

function drag(startX: number, endX: number, panel: ReturnType<typeof useResizablePanelWidth>): void {
  panel.onResizeStart({ clientX: startX } as MouseEvent)
  window.dispatchEvent(new MouseEvent('mousemove', { clientX: endX }))
  window.dispatchEvent(new MouseEvent('mouseup'))
}

describe('useResizablePanelWidth', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('starts at defaultWidth when there is no stored value', () => {
    const { panel } = mountPanel({ defaultWidth: 480 })

    expect(panel.width.value).toBe(480)
  })

  it('docked to "start" (the default): dragging right grows the width', () => {
    const { panel } = mountPanel({ defaultWidth: 480, min: 220 })

    drag(100, 150, panel)

    expect(panel.width.value).toBe(530)
  })

  it('docked to "end": dragging left grows the width', () => {
    const { panel } = mountPanel({ defaultWidth: 480, min: 220, dockedTo: 'end' })

    drag(150, 100, panel)

    expect(panel.width.value).toBe(530)
  })

  it('clamps to min while dragging', () => {
    const { panel } = mountPanel({ defaultWidth: 480, min: 220 })

    drag(500, 100, panel)

    expect(panel.width.value).toBe(220)
  })

  it('clamps to a numeric max while dragging', () => {
    const { panel } = mountPanel({ defaultWidth: 480, max: 600 })

    drag(100, 900, panel)

    expect(panel.width.value).toBe(600)
  })

  it('clamps to a function max, re-evaluated on every move', () => {
    const { panel } = mountPanel({ defaultWidth: 480, max: () => 700 })

    drag(100, 2000, panel)

    expect(panel.width.value).toBe(700)
  })

  it('isResizing toggles true during the drag and false again after mouseup', () => {
    const { panel } = mountPanel({ defaultWidth: 480 })

    panel.onResizeStart({ clientX: 100 } as MouseEvent)
    expect(panel.isResizing.value).toBe(true)

    window.dispatchEvent(new MouseEvent('mouseup'))
    expect(panel.isResizing.value).toBe(false)
  })

  it('stops reacting to further mousemove once unmounted', () => {
    const { panel, wrapper } = mountPanel({ defaultWidth: 480 })
    panel.onResizeStart({ clientX: 100 } as MouseEvent)
    wrapper.unmount()

    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 300 }))

    expect(panel.width.value).toBe(480)
  })

  it('reads a persisted width from localStorage on init, clamped like any other value', () => {
    localStorage.setItem('pdm.console.width', '900')

    const { panel } = mountPanel({ defaultWidth: 480, max: 600, storageKey: 'pdm.console.width' })

    expect(panel.width.value).toBe(600)
  })

  it('ignores a non-numeric stored value and falls back to defaultWidth', () => {
    localStorage.setItem('pdm.console.width', 'not-a-number')

    const { panel } = mountPanel({ defaultWidth: 480, storageKey: 'pdm.console.width' })

    expect(panel.width.value).toBe(480)
  })

  it('persists the width to localStorage once the drag ends', () => {
    const { panel } = mountPanel({ defaultWidth: 480, min: 220, storageKey: 'pdm.console.width' })

    drag(100, 150, panel)

    expect(localStorage.getItem('pdm.console.width')).toBe('530')
  })

  it('does not touch localStorage at all without a storageKey', () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem')
    const { panel } = mountPanel({ defaultWidth: 480 })

    drag(100, 150, panel)

    expect(setItemSpy).not.toHaveBeenCalled()
  })

  it('swallows a localStorage read failure and falls back to defaultWidth', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })

    const { panel } = mountPanel({ defaultWidth: 480, storageKey: 'pdm.console.width' })

    expect(panel.width.value).toBe(480)
  })

  it('swallows a localStorage write failure without throwing', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const { panel } = mountPanel({ defaultWidth: 480, min: 220, storageKey: 'pdm.console.width' })

    expect(() => drag(100, 150, panel)).not.toThrow()
  })
})
