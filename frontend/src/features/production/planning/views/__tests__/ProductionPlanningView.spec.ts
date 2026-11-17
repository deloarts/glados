import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ToastService from 'openvue/toastservice'

import { i18n } from '@/core/i18n'
import { LiveResource } from '@/core/realtime/resources'

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

import ProductionPlanningView from '../ProductionPlanningView.vue'

function mockEmptyBoard(): void {
  getMock.mockImplementation(() => Promise.resolve({ data: { items: [], total: 0 } }))
}

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  return mount(ProductionPlanningView, {
    global: {
      // ToastService alongside pinia/i18n: the view surfaces a
      // failed board load through useErrorToast(), which calls useToast()
      // during setup.
      plugins: [pinia, i18n, ToastService],
      stubs: {
        // AppGanttChart wraps the real @svar-ui widget. It is stubbed so
        // this spec exercises the view's own wiring without a full DOM
        // gantt render.
        AppGanttChart: true,
      },
    },
  })
}

describe('ProductionPlanningView', () => {
  beforeEach(() => {
    getMock.mockReset()
    useLiveRefreshMock.mockReset()
    mockEmptyBoard()
  })

  it('fetches machines and machine pools capped at 500, every open production order page by page, and operators on mount', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/production-machines/', { params: { limit: 500 } })
    expect(getMock).toHaveBeenCalledWith('/production-machine-pools/', { params: { limit: 500 } })
    expect(getMock).toHaveBeenCalledWith('/production-orders/', {
      params: { skip: 0, limit: 500, statuses: ['queued', 'in_progress', 'paused'] },
    })
    expect(getMock).toHaveBeenCalledWith('/production-orders/', {
      params: expect.objectContaining({ skip: 0, limit: 500, statuses: ['completed', 'canceled'] }),
    })
    expect(getMock).toHaveBeenCalledWith('/production-operators/', undefined)

    wrapper.unmount()
  })

  // buildProductionPlanning always pushes an (empty) "No assignment" summary
  // row regardless of how many machines/orders exist (productionPlanningTasks.ts,
  // `pushGroup(machineTaskId(null), noAssignmentLabel, unassignedOrderIds,
  // true)`; the trailing `true` forces it even with zero entries). So the
  // view's own `tasks.length === 0` empty-state branch is unreachable in
  // practice, which is why this test asserts the chart still renders rather
  // than asserting a "shows the empty state" case: that branch can never
  // actually render.
  it('renders AppGanttChart even with zero machines/orders, via the always-present unassigned group', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).not.toContain('No queued, in-progress, or paused orders to plan.')
    const gantt = wrapper.findComponent({ name: 'AppGanttChart' })
    expect(gantt.exists()).toBe(true)
    expect(gantt.props('readonly')).toBe(true)
    expect(gantt.props('tasks')).toHaveLength(1)

    wrapper.unmount()
  })

  it('renders a machine gantt row and its queued order once machines/orders resolve', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-machines/') {
        return Promise.resolve({
          data: {
            items: [
              {
                id: 1,
                internal_name: 'Mill A',
                fabrication_methods: [{ id: 1, name: 'Milling' }],
              },
            ],
            total: 1,
          },
        })
      }
      if (url === '/production-orders/') {
        return Promise.resolve({
          data: {
            items: [
              {
                id: 10,
                production_order_number: 'PO-10',
                status: 'queued',
                machine_id: 1,
                queue_sequence: 1,
                quantity: 10,
                quantity_completed: 0,
                lot_id: 1,
                lot_number: 'LOT-1',
                lot_position_id: 100,
                lot_position_sequence: 1,
                lot_position_count: 1,
                made_item_part_number: 'PN-1',
                made_item_revision: 'A',
                planned_start: '2026-08-01T00:00:00Z',
                planned_end: '2026-08-02T00:00:00Z',
                actual_start: null,
                actual_end: null,
                conflicts: [],
              },
            ],
            total: 1,
          },
        })
      }
      return Promise.resolve({ data: { items: [], total: 0 } })
    })

    const wrapper = mountView()
    await flushPromises()
    await flushPromises()

    const gantt = wrapper.findComponent({ name: 'AppGanttChart' })
    const tasks = gantt.props('tasks') as { id: string; text: string }[]
    // The always-present unassigned-group row, "Mill A"'s own machine group,
    // and PO-10's own bar underneath it.
    expect(tasks.map((t) => t.id)).toEqual(
      expect.arrayContaining(['machine-unassigned', 'machine-1', 'production-order-10']),
    )
    expect(tasks.find((t) => t.id === 'machine-1')?.text).toContain('Mill A')

    wrapper.unmount()
  })

  it('switches the gantt scales when a resolution button is clicked', async () => {
    const wrapper = mountView()
    await flushPromises()

    const gantt = wrapper.findComponent({ name: 'AppGanttChart' })
    const dayScales = gantt.props('scales') as { unit: string }[]
    expect(dayScales.map((s) => s.unit)).toContain('day')

    const monthButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.text() === 'Months')
    expect(monthButton).toBeTruthy()
    await monthButton!.trigger('click')
    await flushPromises()

    const monthScales = wrapper.findComponent({ name: 'AppGanttChart' }).props('scales') as {
      unit: string
    }[]
    expect(monthScales.map((s) => s.unit)).toContain('month')
    expect(monthScales.map((s) => s.unit)).not.toContain('day')

    wrapper.unmount()
  })

  it('wires useLiveRefresh to machines/orders/lots and refetches all of it on its signal', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(useLiveRefreshMock).toHaveBeenCalledTimes(1)
    const [resources, refetch] = useLiveRefreshMock.mock.calls[0]!
    expect(resources).toEqual([
      LiveResource.PRODUCTION_MACHINES,
      LiveResource.PRODUCTION_ORDERS,
      LiveResource.PRODUCTION_LOTS,
    ])

    getMock.mockClear()
    refetch()
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/production-machines/', { params: { limit: 500 } })
    expect(getMock).toHaveBeenCalledWith('/production-orders/', {
      params: { skip: 0, limit: 500, statuses: ['queued', 'in_progress', 'paused'] },
    })

    wrapper.unmount()
  })
})
