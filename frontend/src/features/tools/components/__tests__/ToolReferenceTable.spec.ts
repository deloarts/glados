import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import ToolReferenceTable from '../ToolReferenceTable.vue'
import type { ToolReferenceRow } from '../ToolReferenceTable.vue'

// jsdom has no layout, so the scroll box, its header and its rows get a fake
// one: the box shows 230 px from y = 100, the header is 30 px high, and every
// row is 20 px high and moves up as the box scrolls.
const BOX_TOP = 100
const BOX_HEIGHT = 230
const HEADER = 30
const ROW = 20

function rect(top: number, height: number): DOMRect {
  return { top, bottom: top + height, height, left: 0, right: 0, width: 0, x: 0, y: top, toJSON: () => ({}) }
}

function fakeLayout() {
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
    const box = this.closest<HTMLElement>('[data-testid="ref-scroll-t"]')
    if (!box) return rect(0, 0)
    if (this === box) return rect(BOX_TOP, BOX_HEIGHT)
    if (this.tagName === 'THEAD') return rect(BOX_TOP, HEADER)
    if (this instanceof HTMLTableRowElement && this.parentElement?.tagName === 'TBODY') {
      return rect(BOX_TOP + HEADER + this.sectionRowIndex * ROW - box.scrollTop, ROW)
    }
    return rect(0, 0)
  })
  vi.spyOn(Element.prototype, 'clientHeight', 'get').mockImplementation(function (this: Element) {
    return this.matches('[data-testid="ref-scroll-t"]') ? BOX_HEIGHT : 0
  })
}

function rows(count: number, suffix = ''): ToolReferenceRow[] {
  return Array.from({ length: count }, (_, i) => ({ key: `r${i}`, label: `Row ${i}${suffix}`, cells: [String(i)] }))
}

function mountTable(activeRow: string | null, scrollToActive = true) {
  return mountWithApp(ToolReferenceTable, {
    props: {
      tableKey: 't',
      title: 'Table',
      unit: 'mm',
      rowHeader: 'Row',
      columns: ['Value'],
      rows: rows(40),
      activeRow,
      activeColumn: null,
      scrollToActive,
    },
  })
}

describe('ToolReferenceTable', () => {
  beforeEach(fakeLayout)
  afterEach(() => vi.restoreAllMocks())

  it('marks the active row and moves the mark with it', async () => {
    const wrapper = mountTable('r3', false)

    expect(wrapper.get('[data-testid="ref-row-t"]').text()).toContain('Row 3')
    expect(wrapper.findAll('tr[aria-current="true"]')).toHaveLength(1)

    await wrapper.setProps({ activeRow: 'r7' })

    expect(wrapper.get('[data-testid="ref-row-t"]').text()).toContain('Row 7')
    expect(wrapper.get('[data-testid="ref-row-t"]').attributes('aria-current')).toBe('true')

    await wrapper.setProps({ activeRow: null })

    expect(wrapper.find('[data-testid="ref-row-t"]').exists()).toBe(false)
    expect(wrapper.findAll('tr[aria-current="true"]')).toHaveLength(0)
    wrapper.unmount()
  })

  it('opens with the active row in the middle of its own scroll box', async () => {
    const wrapper = mountTable('r30')
    await flushPromises()

    // Row 30 starts 600 px below the header; the 200 px under the header
    // centre it at 510 px.
    expect(wrapper.get<HTMLElement>('[data-testid="ref-scroll-t"]').element.scrollTop).toBe(510)
    wrapper.unmount()
  })

  it('scrolls only when the active row changes and leaves the box alone otherwise', async () => {
    const wrapper = mountTable('r30')
    await flushPromises()
    const box = wrapper.get<HTMLElement>('[data-testid="ref-scroll-t"]').element
    const scrollTo = vi.fn<(options: ScrollToOptions) => void>()
    box.scrollTo = scrollTo as HTMLElement['scrollTo']

    await wrapper.setProps({ rows: rows(40, ' (renamed)') })
    expect(scrollTo).not.toHaveBeenCalled()

    // Row 32 is already in view, so the box stays where it is.
    await wrapper.setProps({ activeRow: 'r32' })
    expect(scrollTo).not.toHaveBeenCalled()

    await wrapper.setProps({ activeRow: 'r2' })
    expect(scrollTo).toHaveBeenCalledExactlyOnceWith({ top: 0 })
    wrapper.unmount()
  })

  it('does not scroll unless asked to', async () => {
    const wrapper = mountTable('r30', false)
    await flushPromises()

    expect(wrapper.get<HTMLElement>('[data-testid="ref-scroll-t"]').element.scrollTop).toBe(0)
    wrapper.unmount()
  })
})
