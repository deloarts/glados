import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import enGB from '@/core/i18n/locales/en-GB'

import type { ProductionOrderResponse } from '@/features/production'
import type { WipLotResponse } from '@/features/production'
import type { RecentCatalogueItem, StatusCounts } from '../../composables/useDashboardSummary'
import type { TodoTask } from '@/features/todo'

interface DashboardSummaryMock {
  productionQueueStore: { orders: ProductionOrderResponse[] }
  madeDemandCounts: StatusCounts
  boughtDemandCounts: StatusCounts
  sourceDemandCounts: StatusCounts
  wipLots: WipLotResponse[]
  overdueOrders: ProductionOrderResponse[]
  todayOrders: ProductionOrderResponse[]
  recentItems: RecentCatalogueItem[]
  loading: boolean
  inProcessCount: number
  overdueAndTodayCount: number
  activeLotsCount: number
  lotsCount: number
  demandsCount: number
  unreadCount: number
  openDemandsCount: number
  recentOrdersCount: number
  spentRecentlyCents: number
  dailySpendSeries: { day: number; cumulative: number; date: Date }[]
}

interface TodoTasksMock {
  overdue: TodoTask[]
  today: TodoTask[]
  dueNowCount: number
  loading: boolean
}

function emptySummary(overrides: Partial<DashboardSummaryMock> = {}): DashboardSummaryMock {
  return {
    productionQueueStore: { orders: [] },
    madeDemandCounts: {},
    boughtDemandCounts: {},
    sourceDemandCounts: {},
    wipLots: [],
    overdueOrders: [],
    todayOrders: [],
    recentItems: [],
    loading: false,
    inProcessCount: 0,
    overdueAndTodayCount: 0,
    activeLotsCount: 0,
    lotsCount: 0,
    demandsCount: 0,
    unreadCount: 0,
    openDemandsCount: 0,
    recentOrdersCount: 0,
    spentRecentlyCents: 0,
    dailySpendSeries: [],
    ...overrides,
  }
}

function emptyTodo(overrides: Partial<TodoTasksMock> = {}): TodoTasksMock {
  return { overdue: [], today: [], dueNowCount: 0, loading: false, ...overrides }
}

const useDashboardSummaryMock = vi.fn<() => DashboardSummaryMock>()
const useTodoTasksMock = vi.fn<() => TodoTasksMock>()
const productionPlanningEnabledMock = ref(true)

// The dashboard only wires these composables' output into props/tiles; their
// own data-fetching is exercised by their own unit tests,
// not this view spec. Mocking them keeps this spec about the view's own
// responsibility: what it renders from what they hand back.
vi.mock('../../composables/useDashboardSummary', () => ({
  useDashboardSummary: () => useDashboardSummaryMock(),
}))
vi.mock('@/features/todo', () => ({
  useTodoTasks: () => useTodoTasksMock(),
}))
vi.mock('@/core/composables/useProductionPlanning', () => ({
  useProductionPlanning: () => ({ productionPlanningEnabled: productionPlanningEnabledMock }),
}))

import DashboardView from '../DashboardView.vue'

const t = i18n.global.t

const HEAVY_STUBS = {
  ShopFloorPanel: true,
  AlertsPanel: true,
  WipProgressPanel: true,
  DemandPipelinePanel: true,
  SpendingPanel: true,
  RecentItemsPanel: true,
  TodoSummaryPanel: true,
  QuickLinksPanel: true,
}

function mountView(routes: { path: string; name: string }[] = []) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const router = createRouter({
    history: createMemoryHistory(),
    routes: routes.map((r) => ({ ...r, component: { template: '<div />' } })),
  })

  return mountWithApp(DashboardView, {
    pinia,
    global: { plugins: [router], stubs: HEAVY_STUBS },
  })
}

describe('DashboardView', () => {
  beforeEach(() => {
    useDashboardSummaryMock.mockReset()
    useTodoTasksMock.mockReset()
    useDashboardSummaryMock.mockReturnValue(emptySummary())
    useTodoTasksMock.mockReturnValue(emptyTodo())
    productionPlanningEnabledMock.value = true
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("renders DashboardHeader's time-of-day greeting as the page heading", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 7, 11, 10, 0))

    const wrapper = mountView()

    const greetingText = wrapper.find('.dashboard-header-greeting').text()
    expect(enGB.dashboard.greeting.morning).toContain(greetingText)

    wrapper.unmount()
  })

  it('reads the dashboard summary, todo, and production-planning composables on mount', () => {
    const wrapper = mountView()

    expect(useDashboardSummaryMock).toHaveBeenCalledTimes(1)
    expect(useTodoTasksMock).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it('suppresses stat tiles to a loading state while the summary is still loading', () => {
    useDashboardSummaryMock.mockReturnValue(emptySummary({ loading: true }))
    const wrapper = mountView()

    const inProcessTile = wrapper
      .findAllComponents({ name: 'StatTile' })
      .find((tile) => tile.props('label') === t('dashboard.stats.inProcess'))!
    expect(inProcessTile.props('loading')).toBe(true)

    wrapper.unmount()
  })

  it('wires the summary counts and ring maximums into the KPI stat tiles', () => {
    useDashboardSummaryMock.mockReturnValue(
      emptySummary({
        productionQueueStore: { orders: [{ status: 'in_progress' } as ProductionOrderResponse] },
        lotsCount: 12,
        inProcessCount: 3,
        activeLotsCount: 5,
        openDemandsCount: 7,
      }),
    )
    const wrapper = mountView()

    const tiles = wrapper.findAllComponents({ name: 'StatTile' })
    const inProcessTile = tiles.find((tile) => tile.props('label') === t('dashboard.stats.inProcess'))!
    expect(inProcessTile.props('value')).toBe(3)
    expect(inProcessTile.props('ring')).toMatchObject({ max: 1 })

    const activeLotsTile = tiles.find((tile) => tile.props('label') === t('dashboard.stats.activeLots'))!
    expect(activeLotsTile.props('value')).toBe(5)
    expect(activeLotsTile.props('ring')).toMatchObject({ max: 12 })

    wrapper.unmount()
  })

  it('shows the shop-floor and WIP panels only while production planning is enabled', () => {
    productionPlanningEnabledMock.value = false
    const wrapperOff = mountView()
    expect(wrapperOff.findComponent({ name: 'ShopFloorPanel' }).exists()).toBe(false)
    expect(wrapperOff.findComponent({ name: 'WipProgressPanel' }).exists()).toBe(false)
    wrapperOff.unmount()

    productionPlanningEnabledMock.value = true
    const wrapperOn = mountView()
    expect(wrapperOn.findComponent({ name: 'ShopFloorPanel' }).exists()).toBe(true)
    expect(wrapperOn.findComponent({ name: 'WipProgressPanel' }).exists()).toBe(true)
    wrapperOn.unmount()
  })

  it('passes the status counts of each demand kind through to the demand pipeline panel', () => {
    useDashboardSummaryMock.mockReturnValue(
      emptySummary({
        madeDemandCounts: { open: 1 },
        boughtDemandCounts: { ordered: 2 },
        sourceDemandCounts: {},
      }),
    )
    const wrapper = mountView()

    const panel = wrapper.findComponent({ name: 'DemandPipelinePanel' })
    expect(panel.props('madeCounts')).toEqual({ open: 1 })
    expect(panel.props('boughtCounts')).toEqual({ ordered: 2 })
    expect(panel.props('sourceCounts')).toEqual({})

    wrapper.unmount()
  })

  it('navigates to the production queue when the "in process" tile is clicked', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/production', name: 'Production', component: { template: '<div />' } }],
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mountWithApp(DashboardView, {
      pinia,
      global: { plugins: [router], stubs: HEAVY_STUBS },
    })

    const inProcessTile = wrapper
      .findAllComponents({ name: 'StatTile' })
      .find((tile) => tile.props('label') === t('dashboard.stats.inProcess'))!
    await inProcessTile.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/production')

    wrapper.unmount()
  })
})
