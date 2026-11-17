import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'


// The @svar-ui/vue-gantt chain that OrdersTimelineView pulls in only ships
// to users who actually open the timeline tab, so OrdersView wraps it in
// defineAsyncComponent (mirroring ProductionView.vue's asyncTab and
// AppLayout.vue's LotDetailDialog pattern). This spec proves the chunk
// boundary itself, not the gantt-task-building logic (that's
// ordersGanttTasks' own job).

// One order with an ordered_date, enough for buildOrderGanttTasks to emit
// a non-empty task list, so the timeline renders AppGanttChart rather than
// its empty-state.
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
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import OrdersView from '../OrdersView.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/procurement/:section?/:tab?', name: 'Procurement', component: OrdersView }],
})

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  return mountWithApp(OrdersView, {
    pinia,
    global: {
      plugins: [router],
      stubs: {
        RouterLink: true,
        // Out of scope for this spec: only OrdersTimelineView's own lazy
        // loading is under test here.
        OrdersControls: true,
        OrdersViews: true,
        OrdersTable: true,
        // AppGanttChart wraps the real @svar-ui widget, stubbed so this
        // spec exercises the chunk boundary without needing a full DOM
        // gantt render.
        AppGanttChart: true,
      },
    },
  })
}

describe('OrdersView, OrdersTimelineView lazy loading', () => {
  beforeEach(() => {
    getMock.mockReset()
    getMock.mockImplementation((url: string) => {
      if (url === '/orders/') {
        return Promise.resolve({ data: { items: [ORDER], total: 1, limit: 200, skip: 0 } })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })
  })

  it('does not mount OrdersTimelineView synchronously when the timeline tab is opened', async () => {
    await router.push('/procurement/orders/timeline')
    const wrapper = mountView()

    // No flushPromises/waitFor here on purpose: the dynamic import needs
    // real macrotasks to resolve, so an unresolved chunk must show neither
    // the view nor the chart synchronously.
    expect(wrapper.findComponent({ name: 'OrdersTimelineView' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'AppGanttChart' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('resolves OrdersTimelineView once the chunk loads, mounting AppGanttChart', async () => {
    await router.push('/procurement/orders/timeline')
    const wrapper = mountView()

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'OrdersTimelineView' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    await flushPromises()

    expect(wrapper.findComponent({ name: 'AppGanttChart' }).exists()).toBe(true)

    wrapper.unmount()
  })

  it('does not mount OrdersTimelineView on the plain orders tab', async () => {
    await router.push('/procurement/orders')
    const wrapper = mountView()
    await flushPromises()
    await flushPromises()

    expect(wrapper.findComponent({ name: 'OrdersTimelineView' }).exists()).toBe(false)

    wrapper.unmount()
  })
})
