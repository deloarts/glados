import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref, useTemplateRef } from 'vue'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'

import { useControlsBarFit } from '../useControlsBarFit'

// jsdom lays nothing out, so the spec gives every element a width in a data
// attribute and wraps the items of the start group the way a wrapping flex
// row would, 40px per row.

const ROW_HEIGHT = 40

function layout(element: HTMLElement): DOMRect {
  const width = Number(element.dataset.width ?? 0)
  const group = element.parentElement
  if (!group?.classList.contains('controls-bar-start')) {
    return new DOMRect(0, 0, width, ROW_HEIGHT)
  }
  const available = Number(group.dataset.width)
  let x = 0
  let row = 0
  for (const item of Array.from(group.children) as HTMLElement[]) {
    const itemWidth = Number(item.dataset.width)
    if (x > 0 && x + itemWidth > available) {
      x = 0
      row += 1
    }
    if (item === element) return new DOMRect(x, row * ROW_HEIGHT, itemWidth, ROW_HEIGHT)
    x += itemWidth
  }
  return new DOMRect(0, 0, 0, 0)
}

let resize: () => void = () => {}
const OriginalResizeObserver = globalThis.ResizeObserver

beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (
    this: HTMLElement,
  ) {
    return layout(this)
  })
  vi.spyOn(HTMLElement.prototype, 'getClientRects').mockImplementation(function (
    this: HTMLElement,
  ) {
    return [layout(this)] as unknown as DOMRectList
  })
  vi.stubGlobal(
    'ResizeObserver',
    class {
      constructor(callback: () => void) {
        resize = callback
      }
      observe(): void {}
      unobserve(): void {}
      disconnect(): void {}
    },
  )
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.stubGlobal('ResizeObserver', OriginalResizeObserver)
})

/**
 * A bar with a fixed 100px button and three groups. Spread out, a group is
 * three 100px buttons; collapsed, one 60px menu button.
 */
async function mountBar(width: number) {
  const barWidth = ref(width)
  let collapsed = ref(0) as { readonly value: number }
  const wrapper = mountWithApp(
    defineComponent({
      setup() {
        const bar = useTemplateRef<HTMLElement>('bar')
        collapsed = useControlsBarFit(bar, ['first', 'second', 'third']).collapsedGroups
        return () =>
          h('div', { ref: 'bar' }, [
            h('div', { class: 'controls-bar-start', 'data-width': barWidth.value }, [
              h('button', { 'data-width': 100 }),
              ...[0, 1, 2].flatMap((group) =>
                collapsed.value > group
                  ? [h('button', { 'data-width': 60 })]
                  : [0, 1, 2].map(() => h('button', { 'data-width': 100 })),
              ),
            ]),
          ])
      },
    }),
  )
  await flushPromises()
  resize()
  await flushPromises()
  return {
    collapsed: () => collapsed.value,
    async resizeTo(next: number) {
      barWidth.value = next
      await flushPromises()
      resize()
      await flushPromises()
    },
    wrapper,
  }
}

describe('useControlsBarFit', () => {
  it('keeps every group spread out while the buttons fit on one row', async () => {
    const bar = await mountBar(1000)

    expect(bar.collapsed()).toBe(0)
    bar.wrapper.unmount()
  })

  it('collapses the groups in order until the buttons fit', async () => {
    // Spread out the buttons need 1000px, one group collapsed 760px, two 520px.
    const bar = await mountBar(800)
    expect(bar.collapsed()).toBe(1)

    await bar.resizeTo(600)
    expect(bar.collapsed()).toBe(2)

    await bar.resizeTo(300)
    expect(bar.collapsed()).toBe(3)
    bar.wrapper.unmount()
  })

  it('spreads a group out again only once the width it needed is free', async () => {
    const bar = await mountBar(600)
    expect(bar.collapsed()).toBe(2)

    await bar.resizeTo(700)
    expect(bar.collapsed()).toBe(2)

    await bar.resizeTo(760)
    expect(bar.collapsed()).toBe(1)

    await bar.resizeTo(1000)
    expect(bar.collapsed()).toBe(0)
    bar.wrapper.unmount()
  })

  it('collapses nothing before the bar has a width', async () => {
    const bar = await mountBar(0)

    expect(bar.collapsed()).toBe(0)
    bar.wrapper.unmount()
  })
})
