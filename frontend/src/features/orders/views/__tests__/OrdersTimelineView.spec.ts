import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { LiveResource } from '@/core/realtime/resources'
import { useOrdersFiltersStore } from '../../stores/ordersFiltersStore'

// One order with an ordered_date, enough for buildOrderGanttTasks to emit a
// non-empty task list, so the timeline renders AppGanttChart rather than its
// empty-state. Mirrors OrdersView.spec.ts's own fixture.
const ORDER = {
  id: 1,
  order_number: 'ORD-1',
  status: 'ordered',
  created: '2026-08-01T00:00:00Z',
  changed: null,
  total: null,
  note: null,
  ordered_date: '2026-08-01T00:00:00Z',
  expected_delivery_date: null,
  delivery_date: null,
  storage_place: null,
  creator_id: 1,
  creator: null,
  supplier_id: 1,
  supplier_name: 'Acme',
  supplier_vat_id: '',
  items: [],
}

const getMock =
  vi.fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => getMock(url, config),
  },
}))

// The established convention (see ProductionCapacityView.spec.ts,
// MachineDetailContent.spec.ts) is to replace useLiveRefresh wholesale
// rather than drive its real 500ms debounce; this captures what it was
// called with so the resource list and the refetch wiring are still provable.
const useLiveRefreshMock =
  vi.fn<(resources: string[], refetch: () => void) => void>()
vi.mock('@/core/realtime/useLiveRefresh', () => ({
  useLiveRefresh: (resources: string[], refetch: () => void) =>
    useLiveRefreshMock(resources, refetch),
}))

import OrdersTimelineView from '../OrdersTimelineView.vue'

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  return mount(OrdersTimelineView, {
    global: {
      plugins: [pinia, i18n],
      stubs: {
        // AppGanttChart wraps the real @svar-ui widget, stubbed so this
        // spec exercises the view's own wiring without needing a full DOM
        // gantt render.
        AppGanttChart: true,
      },
    },
  })
}

describe('OrdersTimelineView', () => {
  beforeEach(() => {
    getMock.mockReset()
    useLiveRefreshMock.mockReset()
    getMock.mockImplementation((url: string) => {
      if (url === '/orders/') {
        return Promise.resolve({ data: { items: [ORDER], total: 1, limit: 200, skip: 0 } })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })
  })

  // PageLayout's own `title` prop is deliberately omitted here (see its doc
  // comment); OrdersTimelineView is only ever mounted as a nested panel
  // inside OrdersView's own PageLayout, which already carries the page's one
  // heading. Asserting a second h1 here would be asserting a bug, not a
  // feature; this only proves the view stays that way.
  it('renders no heading of its own - the parent OrdersView owns the page title', () => {
    const wrapper = mountView()

    expect(wrapper.find('h1').exists()).toBe(false)
  })

  it('fetches the orders timeline on mount with a 200-row limit', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/orders/', { params: { limit: 200 } })

    wrapper.unmount()
  })

  it('shows the empty state and no gantt chart when there are no dated orders', async () => {
    getMock.mockImplementation(() =>
      Promise.resolve({ data: { items: [], total: 0, limit: 200, skip: 0 } }),
    )

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('No orders with dates to show yet.')
    expect(wrapper.findComponent({ name: 'AppGanttChart' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('renders AppGanttChart with built tasks and columns once orders resolve', async () => {
    const wrapper = mountView()
    await flushPromises()

    const gantt = wrapper.findComponent({ name: 'AppGanttChart' })
    expect(gantt.exists()).toBe(true)
    expect(gantt.props('readonly')).toBe(true)
    expect(gantt.props('tasks')).toHaveLength(1)
    expect((gantt.props('columns') as { id: string }[]).map((c) => c.id)).toEqual([
      'text',
      'status',
      'start',
      'duration',
    ])

    wrapper.unmount()
  })

  it('refetches when the orders store refresh trigger bumps (e.g. after a create/update elsewhere)', async () => {
    const wrapper = mountView()
    await flushPromises()
    getMock.mockClear()

    const { useOrdersStore } = await import('../../stores/ordersStore')
    useOrdersStore().triggerRefresh()
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/orders/', { params: { limit: 200 } })

    wrapper.unmount()
  })

  it('filters out delivered/canceled orders from the timeline when those filters are on', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/orders/') {
        return Promise.resolve({
          data: {
            items: [
              ORDER,
              { ...ORDER, id: 2, order_number: 'ORD-2', status: 'delivered' },
            ],
            total: 2,
            limit: 200,
            skip: 0,
          },
        })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    const pinia = createPinia()
    setActivePinia(pinia)
    useOrdersFiltersStore().hideDelivered = true

    const wrapper = mount(OrdersTimelineView, {
      global: { plugins: [pinia, i18n], stubs: { AppGanttChart: true } },
    })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'AppGanttChart' }).props('tasks')).toHaveLength(1)

    wrapper.unmount()
  })

  it('wires useLiveRefresh to the ORDERS resource and refetches on its signal', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(useLiveRefreshMock).toHaveBeenCalledTimes(1)
    const [resources, refetch] = useLiveRefreshMock.mock.calls[0]!
    expect(resources).toEqual([LiveResource.ORDERS])

    getMock.mockClear()
    refetch()
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/orders/', { params: { limit: 200 } })

    wrapper.unmount()
  })
})
