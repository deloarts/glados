import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { LiveResource } from '@/core/realtime/resources'
import { useProductionLotsFiltersStore } from '../../stores/productionLotsFiltersStore'

// One lot with a single external (no production-order fetch needed)
// position, resolvable straight from expected_delivery_date, enough for
// buildLotGanttTasks to emit a non-empty task list, so the timeline renders
// AppGanttChart rather than its empty-state. Mirrors
// ProductionLotsListView.timelineLazyLoad.spec.ts's own fixture.
const FULL_LOT = {
  id: 1,
  lot_number: 'LOT-1',
  made_item_part_number: 'PN-1',
  status: 'in_progress',
  steps: [{ id: 10, position_id: 100, role: 'fabrication', fabrication_method_name: 'Milling' }],
  positions: [{ id: 100, kind: 'external', expected_delivery_date: '2026-08-01T00:00:00Z' }],
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

import LotsTimelineView from '../LotsTimelineView.vue'

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  return mount(LotsTimelineView, {
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

function mockDefaultLotsList(): void {
  getMock.mockImplementation((url: string) => {
    if (url === '/production-lots/') {
      return Promise.resolve({ data: { items: [{ id: 1 }], total: 1, limit: 50, skip: 0 } })
    }
    if (url === '/production-lots/1') {
      return Promise.resolve({ data: FULL_LOT })
    }
    return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
  })
}

describe('LotsTimelineView', () => {
  beforeEach(() => {
    getMock.mockReset()
    useLiveRefreshMock.mockReset()
    mockDefaultLotsList()
  })

  // Same reasoning as OrdersTimelineView.spec.ts: PageLayout's `title` is
  // deliberately omitted (see its own doc comment), this view is only ever
  // a nested panel inside ProductionLotsListView's own PageLayout.
  it('renders no heading of its own - the parent lots list view owns the page title', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('h1').exists()).toBe(false)

    wrapper.unmount()
  })

  it('fetches the lots timeline on mount with a 50-row limit, then the full detail per lot', async () => {
    const wrapper = mountView()
    await flushPromises()
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/production-lots/', { params: { limit: 50 } })
    expect(getMock).toHaveBeenCalledWith('/production-lots/1', undefined)

    wrapper.unmount()
  })

  it('shows the empty state and no gantt chart when there are no scheduled lots', async () => {
    getMock.mockImplementation(() =>
      Promise.resolve({ data: { items: [], total: 0, limit: 50, skip: 0 } }),
    )

    const wrapper = mountView()
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('No lots to show yet.')
    expect(wrapper.findComponent({ name: 'AppGanttChart' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('renders AppGanttChart with built tasks and columns once lot schedules resolve', async () => {
    const wrapper = mountView()
    await flushPromises()
    await flushPromises()

    const gantt = wrapper.findComponent({ name: 'AppGanttChart' })
    expect(gantt.exists()).toBe(true)
    expect(gantt.props('readonly')).toBe(true)
    // One summary row for the lot itself plus one row for its single
    // scheduled step (buildLotGanttTasks' own lot-summary/lot-step split).
    expect(gantt.props('tasks')).toHaveLength(2)
    expect((gantt.props('columns') as { id: string }[]).map((c) => c.id)).toEqual([
      'text',
      'status',
      'start',
      'duration',
    ])

    wrapper.unmount()
  })

  it('refetches when the lots store refresh trigger bumps (e.g. after a create/update elsewhere)', async () => {
    const wrapper = mountView()
    await flushPromises()
    await flushPromises()
    getMock.mockClear()

    const { useProductionLotsStore } = await import('../../../stores/productionLotsStore')
    useProductionLotsStore().triggerRefresh()
    await flushPromises()
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/production-lots/', { params: { limit: 50 } })

    wrapper.unmount()
  })

  it('excludes completed lots once hideCompleted is on, re-fetching the full detail set', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/') {
        return Promise.resolve({
          data: {
            items: [{ id: 1 }, { id: 2, status: 'completed' }],
            total: 2,
            limit: 50,
            skip: 0,
          },
        })
      }
      if (url === '/production-lots/1') return Promise.resolve({ data: FULL_LOT })
      if (url === '/production-lots/2') {
        return Promise.resolve({
          data: { ...FULL_LOT, id: 2, lot_number: 'LOT-2', status: 'completed' },
        })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })

    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(LotsTimelineView, {
      global: { plugins: [pinia, i18n], stubs: { AppGanttChart: true } },
    })
    await flushPromises()
    await flushPromises()

    // Both lots are unfiltered here (hideCompleted is off by default), so
    // both full-detail fetches fire and both feed lot-summary + lot-step
    // gantt rows.
    expect(getMock).toHaveBeenCalledWith('/production-lots/2', undefined)
    expect(wrapper.findComponent({ name: 'AppGanttChart' }).props('tasks')).toHaveLength(4)

    getMock.mockClear()
    useProductionLotsFiltersStore().hideCompleted = true
    await flushPromises()
    await flushPromises()

    // Re-running the fetch entirely (not just re-filtering client side): lot
    // 2's full detail is never requested again once excluded up front.
    expect(getMock).not.toHaveBeenCalledWith('/production-lots/2', undefined)
    expect(wrapper.findComponent({ name: 'AppGanttChart' }).props('tasks')).toHaveLength(2)

    wrapper.unmount()
  })

  it('wires useLiveRefresh to PRODUCTION_LOTS and PRODUCTION_ORDERS, and refetches on its signal', async () => {
    const wrapper = mountView()
    await flushPromises()
    await flushPromises()

    expect(useLiveRefreshMock).toHaveBeenCalledTimes(1)
    const [resources, refetch] = useLiveRefreshMock.mock.calls[0]!
    expect(resources).toEqual([LiveResource.PRODUCTION_LOTS, LiveResource.PRODUCTION_ORDERS])

    getMock.mockClear()
    refetch()
    await flushPromises()
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/production-lots/', { params: { limit: 50 } })

    wrapper.unmount()
  })
})
