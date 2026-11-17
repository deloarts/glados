import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'

import type { DashboardSummaryResponse } from '../../types/dashboardSummaryResponse'

const getDashboardSummaryMock = vi.fn<() => Promise<DashboardSummaryResponse>>()
vi.mock('../../api/getDashboardSummary', () => ({
  getDashboardSummary: () => getDashboardSummaryMock(),
}))

const liveRefresh: { resources: string[]; refetch: () => unknown }[] = []
vi.mock('@/core/realtime/useLiveRefresh', () => ({
  useLiveRefresh: (resources: string[], refetch: () => unknown) =>
    liveRefresh.push({ resources, refetch }),
}))

vi.mock('@/features/production', () => ({
  useProductionQueueStore: () => ({
    machines: [],
    orders: [],
    loading: false,
    fetchAll: () => Promise.resolve(),
  }),
  useProductionSchedule: () => ({
    lotsById: ref(new Map()),
    orderedDateByPositionId: ref(new Map()),
  }),
  computeProductionSchedule: () => new Map(),
  getProductionWip: () => Promise.resolve([]),
}))
vi.mock('@/features/notifications', () => ({
  useNotificationsStore: () => ({ unreadCount: 0 }),
}))
vi.mock('@/features/made-items', () => ({
  getMadeItems: () => Promise.resolve({ items: [], total: 0 }),
}))
vi.mock('@/features/bought-items', () => ({
  getBoughtItems: () => Promise.resolve({ items: [], total: 0 }),
}))

import { useDashboardSummary } from '../useDashboardSummary'

function summary(overrides: Partial<DashboardSummaryResponse> = {}): DashboardSummaryResponse {
  return {
    lots: [
      { status: 'planned', count: 3 },
      { status: 'completed', count: 4 },
      { status: 'canceled', count: 1 },
      { status: 'scrapped', count: 2 },
    ],
    bought_demands: [
      { status: 'open', count: 2 },
      { status: 'fulfilled', count: 5 },
    ],
    made_demands: [{ status: 'open', count: 1 }],
    source_demands: [],
    spend: {
      window_from: '2026-10-06',
      window_to: '2026-10-08',
      order_count: 3,
      net_total: 4500,
      days: [
        { day: '2026-10-06', net_total: 1000 },
        { day: '2026-10-07', net_total: 0 },
        { day: '2026-10-08', net_total: 3500 },
      ],
    },
    ...overrides,
  }
}

function mountComposable() {
  let result: ReturnType<typeof useDashboardSummary> | undefined
  const wrapper = mount(
    defineComponent({
      setup() {
        result = useDashboardSummary()
        return () => h('div')
      },
    }),
  )
  return { wrapper, summary: () => result! }
}

describe('useDashboardSummary', () => {
  beforeEach(() => {
    getDashboardSummaryMock.mockReset()
    liveRefresh.splice(0)
  })

  it('reads the counts and the spend from the server summary', async () => {
    getDashboardSummaryMock.mockResolvedValue(summary())

    const { wrapper, summary: s } = mountComposable()
    await flushPromises()

    expect(getDashboardSummaryMock).toHaveBeenCalledTimes(1)
    expect(s().lotsCount.value).toBe(10)
    // Every lot that is neither completed nor canceled counts as active.
    expect(s().activeLotsCount.value).toBe(5)
    expect(s().demandsCount.value).toBe(8)
    expect(s().openDemandsCount.value).toBe(3)
    expect(s().boughtDemandCounts.value).toEqual({ open: 2, fulfilled: 5 })
    expect(s().recentOrdersCount.value).toBe(3)
    expect(s().spentRecentlyCents.value).toBe(4500)
    expect(s().dailySpendSeries.value.map((p) => [p.day, p.cumulative])).toEqual([
      [1, 1000],
      [2, 1000],
      [3, 4500],
    ])
    expect(s().dailySpendSeries.value[2]?.date).toEqual(new Date(2026, 9, 8))

    wrapper.unmount()
  })

  it('refetches the summary when a counted list changes, without a loading state', async () => {
    getDashboardSummaryMock.mockResolvedValue(summary())
    const { wrapper, summary: s } = mountComposable()
    await flushPromises()

    expect(liveRefresh).toHaveLength(1)
    expect(liveRefresh[0]?.resources).toEqual([
      'production-lots',
      'bought-items-demands',
      'made-items-demands',
      'source-item-demands',
      'orders',
    ])

    getDashboardSummaryMock.mockResolvedValue(summary({ lots: [{ status: 'draft', count: 1 }] }))
    const refetch = liveRefresh[0]!.refetch()
    expect(s().loading.value).toBe(false)
    await refetch
    await flushPromises()

    expect(s().lotsCount.value).toBe(1)

    wrapper.unmount()
  })
})
