import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { LiveResource } from '@/core/realtime/resources'
import { useQaFiltersStore } from '../../stores/qaFiltersStore'

function makeTask(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    production_order_id: 10,
    production_order_number: 'PO-10',
    lot_id: 1,
    lot_number: 'LOT-1',
    made_item_part_number: 'PN-1',
    made_item_revision: 'A',
    inspection_method_name: 'Visual Check',
    quantity: 10,
    can_start: true,
    requires_evidence: false,
    has_evidence: false,
    planned_start: null,
    ...overrides,
  }
}

const getMock =
  vi.fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => getMock(url, config),
  },
}))

// Same convention as OrdersTimelineView.spec.ts/ProductionCapacityView.spec.ts:
// useLiveRefresh is replaced wholesale rather than driving its real 500ms
// debounce, capturing what it was called with instead.
const useLiveRefreshMock = vi.fn<(resources: string[], refetch: () => void) => void>()
vi.mock('@/core/realtime/useLiveRefresh', () => ({
  useLiveRefresh: (resources: string[], refetch: () => void) =>
    useLiveRefreshMock(resources, refetch),
}))

import ProductionQaView from '../ProductionQaView.vue'

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  return mount(ProductionQaView, {
    global: {
      plugins: [pinia, i18n],
      stubs: {
        QaControls: true,
        QaViews: true,
        // The DataTable itself is out of scope here; only the view's own
        // fetch/pagination wiring is under test.
        QaTaskTable: true,
      },
    },
  })
}

describe('ProductionQaView', () => {
  beforeEach(() => {
    getMock.mockReset()
    useLiveRefreshMock.mockReset()
    getMock.mockImplementation(() =>
      Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } }),
    )
  })

  it('fetches the first page of QA tasks on mount with the default filters', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/production-qa/', {
      params: {
        include_completed: false,
        include_canceled: false,
        include_future: false,
        skip: 0,
        limit: 25,
      },
    })

    wrapper.unmount()
  })

  it('passes the page window down to QaTaskTable', async () => {
    getMock.mockImplementation(() =>
      Promise.resolve({ data: { items: [makeTask()], total: 1, limit: 25, skip: 0 } }),
    )

    const wrapper = mountView()
    await flushPromises()

    const table = wrapper.findComponent({ name: 'QaTaskTable' })
    expect(table.props('first')).toBe(0)
    expect(table.props('rows')).toBe(25)
  })

  it('resets to page 0 and refetches when a filter changes', async () => {
    const wrapper = mountView()
    await flushPromises()

    const table = wrapper.findComponent({ name: 'QaTaskTable' })
    table.vm.$emit('page', { first: 25, rows: 25 })
    await flushPromises()
    expect(getMock).toHaveBeenLastCalledWith('/production-qa/', {
      params: expect.objectContaining({ skip: 25 }),
    })

    getMock.mockClear()
    useQaFiltersStore().showCompleted = true
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/production-qa/', {
      params: expect.objectContaining({ include_completed: true, skip: 0 }),
    })

    wrapper.unmount()
  })

  it('wires useLiveRefresh to production orders/lots and refetches the current page on its signal', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(useLiveRefreshMock).toHaveBeenCalledTimes(1)
    const [resources, refetch] = useLiveRefreshMock.mock.calls[0]!
    expect(resources).toEqual([LiveResource.PRODUCTION_ORDERS, LiveResource.PRODUCTION_LOTS])

    getMock.mockClear()
    refetch()
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/production-qa/', {
      params: expect.objectContaining({ skip: 0, limit: 25 }),
    })

    wrapper.unmount()
  })
})
