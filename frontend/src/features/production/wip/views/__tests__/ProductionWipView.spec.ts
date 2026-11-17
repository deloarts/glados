import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { WipLotResponse } from '../../types/productionWipResponse'

const getMock = vi.fn<() => Promise<unknown>>()
vi.mock('@/core/api', () => ({
  default: { get: (...args: unknown[]) => getMock(...(args as [])) },
}))

import ProductionWipView from '../ProductionWipView.vue'

function makeLot(overrides: Partial<WipLotResponse> = {}): WipLotResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    lot_number: 'LOT-0001',
    quantity: 10,
    status: 'in_progress',
    priority: 'high',
    made_item_id: 1,
    made_item_part_number: 'PN-001',
    made_item_revision: 'A',
    made_item_article_name: 'Widget',
    raw_count: 3,
    finished_count: 4,
    stages: [],
    ...overrides,
  }
}

describe('ProductionWipView', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    getMock.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // The WIP view renders inside PageLayout like its sibling production tabs
  // (queue, planning, capacity, QA), not as a bare <h2> + status span.
  it('renders inside PageLayout (card disabled) and shows the WIP table content', async () => {
    getMock.mockResolvedValue({ data: [makeLot()] })

    const wrapper = mountWithApp(ProductionWipView)
    await flushPromises()

    const layout = wrapper.findComponent({ name: 'PageLayout' })
    expect(layout.exists()).toBe(true)
    expect(layout.props('card')).toBe(false)
    expect(wrapper.text()).toContain('LOT-0001')
    expect(wrapper.text()).toContain('Widget')

    wrapper.unmount()
  })

  it('surfaces a manual sync control that re-fetches the WIP list', async () => {
    getMock.mockResolvedValue({ data: [] })

    const wrapper = mountWithApp(ProductionWipView)
    await flushPromises()

    const viewsBar = wrapper.findComponent({ name: 'ViewsBar' })
    expect(viewsBar.exists()).toBe(true)

    getMock.mockClear()
    viewsBar.vm.$emit('sync')
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/production-wip/')

    wrapper.unmount()
  })

  it('keeps the rows on screen when a refetch fails', async () => {
    getMock.mockResolvedValue({ data: [makeLot()] })
    const wrapper = mountWithApp(ProductionWipView)
    await flushPromises()

    getMock.mockRejectedValue(new Error('offline'))
    wrapper.findComponent({ name: 'ViewsBar' }).vm.$emit('sync')
    await flushPromises()

    expect(getMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('LOT-0001')

    wrapper.unmount()
  })

  it('refreshes from live signals only, without a timer poll', async () => {
    getMock.mockResolvedValue({ data: [] })
    const wrapper = mountWithApp(ProductionWipView)
    await flushPromises()

    getMock.mockClear()
    await vi.advanceTimersByTimeAsync(60_000)

    expect(getMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })
})
