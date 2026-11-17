import { describe, it, expect, vi, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { RouteStub, makeTestRouter } from '@/test-utils/factories'

import type {
  ProductionKpiEstimateAccuracyResult,
  ProductionKpiLateLotsResult,
  ProductionKpiQualityByItemResult,
  ProductionKpiSummaryResult,
  ProductionKpiUtilizationResult,
  ProductionKpiWaitingTimeResult,
  ProductionKpiWeeklyResult,
} from '../../types/productionKpiResponse'

function emptyPage() {
  return { items: [], total: 0, limit: 500, skip: 0 }
}

const summaryFixture: ProductionKpiSummaryResult = {
  schedule_adherence: { value: 0.8, numerator: 8, denominator: 10 },
  on_time_delivery: { value: 0.75, numerator: 6, denominator: 8 },
  throughput_time: { median_days: 5.5, p90_days: 9.2, count: 12 },
  first_pass_yield: { value: 0.95, numerator: 190, denominator: 200 },
  scrap_ratio: { value: 0.02, numerator: 4, denominator: 200 },
  rework_ratio: { value: 0.03, numerator: 6, denominator: 200 },
  utilization: { value: 0.7, numerator: 700, denominator: 1000 },
  availability: { value: 0.9, numerator: 900, denominator: 1000 },
  oee: 0.6,
}

const weeklyFixture: ProductionKpiWeeklyResult = {
  points: [
    {
      iso_week: '2026-W38',
      week_start: '2026-09-14',
      schedule_adherence: { value: 0.8, numerator: 4, denominator: 5 },
      on_time_delivery: { value: 0.6, numerator: 3, denominator: 5 },
    },
  ],
}

const utilizationFixture: ProductionKpiUtilizationResult = {
  rows: [
    {
      machine_id: 1,
      machine_internal_name: 'CNC-01',
      net_minutes: 700,
      available_minutes: 1000,
      utilization: { value: 0.7, numerator: 700, denominator: 1000 },
      downtime_minutes: 100,
      availability: { value: 0.9, numerator: 900, denominator: 1000 },
    },
  ],
}

const estimateAccuracyFixture: ProductionKpiEstimateAccuracyResult = {
  rows: [{ fabrication_method_id: 1, fabrication_method_name: { enGB: 'Milling' }, median_ratio: 1.1, count: 5 }],
}

const waitingTimeFixture: ProductionKpiWaitingTimeResult = {
  rows: [{ position_kind: 'internal', median_days: 1.5, count: 3 }],
}

const lateLotsFixture: ProductionKpiLateLotsResult = {
  rows: [
    {
      lot_id: 101,
      lot_number: 'LOT-101',
      target_date: '2026-09-10',
      projected_end: '2026-09-15',
      days_late: 5,
      driver_reason: 'missing_material',
      driver_date: '2026-09-15',
    },
  ],
}

const qualityByItemFixture: ProductionKpiQualityByItemResult = {
  rows: [
    {
      made_item_id: 5,
      made_item_part_number: 'PN-5',
      made_item_article_name: 'Bracket',
      completed: 200,
      rejected: 10,
      rework: 6,
      scrap: 4,
      yield_ratio: { value: 0.95, numerator: 190, denominator: 200 },
    },
  ],
}

const ROUTES: Record<string, unknown> = {
  '/production-kpi/summary': summaryFixture,
  '/production-kpi/weekly': weeklyFixture,
  '/production-kpi/utilization': utilizationFixture,
  '/production-kpi/estimate-accuracy': estimateAccuracyFixture,
  '/production-kpi/waiting-time': waitingTimeFixture,
  '/production-kpi/late-lots': lateLotsFixture,
  '/production-kpi/quality-by-item': qualityByItemFixture,
  '/production-machines/': emptyPage(),
  '/production-machine-pools/': emptyPage(),
  '/projects/': emptyPage(),
  '/customers/': emptyPage(),
}

const EMPTY_ROUTES: Record<string, unknown> = {
  '/production-kpi/summary': {
    schedule_adherence: { value: null, numerator: 0, denominator: 0 },
    on_time_delivery: { value: null, numerator: 0, denominator: 0 },
    throughput_time: { median_days: null, p90_days: null, count: 0 },
    first_pass_yield: { value: null, numerator: 0, denominator: 0 },
    scrap_ratio: { value: null, numerator: 0, denominator: 0 },
    rework_ratio: { value: null, numerator: 0, denominator: 0 },
    utilization: null,
    availability: null,
    oee: null,
  } satisfies ProductionKpiSummaryResult,
  '/production-kpi/weekly': { points: [] } satisfies ProductionKpiWeeklyResult,
  '/production-kpi/utilization': { rows: [] } satisfies ProductionKpiUtilizationResult,
  '/production-kpi/estimate-accuracy': { rows: [] } satisfies ProductionKpiEstimateAccuracyResult,
  '/production-kpi/waiting-time': { rows: [] } satisfies ProductionKpiWaitingTimeResult,
  '/production-kpi/late-lots': { rows: [] } satisfies ProductionKpiLateLotsResult,
  '/production-kpi/quality-by-item': { rows: [] } satisfies ProductionKpiQualityByItemResult,
  '/production-machines/': emptyPage(),
  '/production-machine-pools/': emptyPage(),
  '/projects/': emptyPage(),
  '/customers/': emptyPage(),
}

let activeRoutes = ROUTES

const getMock = vi.fn<(url: string) => Promise<{ data: unknown }>>().mockImplementation((url: string) => {
  if (url in activeRoutes) return Promise.resolve({ data: activeRoutes[url] })
  return Promise.reject(new Error(`unexpected GET ${url}`))
})

vi.mock('@/core/api', () => ({
  default: { get: (url: string) => getMock(url) },
}))

// Chart.js needs a canvas context jsdom doesn't provide, stubbed the same
// way SpendLineChart.spec.ts does, purely to avoid the mount crashing.
const chartStub = {
  name: 'Chart',
  props: ['data', 'options', 'type'],
  template: '<div class="chart-stub" />',
}

import ProductionKpiView from '../ProductionKpiView.vue'

function makeRouter() {
  return makeTestRouter([{ path: '/production/lots/:id(\\d+)', component: RouteStub }])
}

async function mountView() {
  const router = makeRouter()
  await router.push('/')
  await router.isReady()

  const wrapper = mountWithApp(ProductionKpiView, {
    global: {
      plugins: [router],
      stubs: { Chart: chartStub },
    },
  })
  // Several independent async trees resolve here (the store's own
  // Promise.all plus KpiFiltersBar's machine/pool/project/customer
  // fetches), each a few microtask hops deep; flush more than once so
  // every one of them has settled before assertions run.
  for (let i = 0; i < 4; i++) {
    await flushPromises()
  }
  return wrapper
}

describe('ProductionKpiView', () => {
  afterEach(() => {
    activeRoutes = ROUTES
    i18n.global.locale.value = 'enGB'
  })

  it('renders tiles, charts and tables from a fixture', async () => {
    const wrapper = await mountView()

    // Tiles
    expect(wrapper.text()).toContain('Schedule Adherence')
    expect(wrapper.text()).toContain('80.0%')
    expect(wrapper.text()).toContain('On-Time Delivery')
    expect(wrapper.text()).toContain('75.0%')
    expect(wrapper.text()).toContain('OEE')
    expect(wrapper.text()).toContain('60.0%')

    // Charts mounted (stubbed) rather than skipped as empty
    expect(wrapper.findAllComponents({ name: 'Chart' }).length).toBe(2)

    // Estimate accuracy panel
    expect(wrapper.text()).toContain('Milling')

    // Waiting time panel (position kind translated via production.lots.positionKind)
    expect(wrapper.text()).toContain('Internal')

    // Late lots table: lot number as a RouterLink to the lot detail
    const lotLink = wrapper.find('a.lot-link')
    expect(lotLink.exists()).toBe(true)
    expect(lotLink.text()).toBe('LOT-101')
    expect(lotLink.attributes('href')).toBe('/production/lots/101')
    expect(wrapper.text()).toContain('Missing material')

    // Quality by item table
    expect(wrapper.text()).toContain('PN-5')
    expect(wrapper.text()).toContain('Bracket')
  })

  it('renders explicit empty states, never a blank chart or table, when nothing matches', async () => {
    activeRoutes = EMPTY_ROUTES
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('n/a')
    expect(wrapper.text()).toContain('No completed orders with a recorded planned-end baseline in this period.')

    // No availability/OEE tile at all when neither is computable.
    expect(wrapper.text()).not.toContain('OEE')

    expect(wrapper.text()).toContain('No data in this period.')
    expect(wrapper.text()).toContain('No machine data in this period.')
    expect(wrapper.text()).toContain('No completed orders with an estimate in this period.')
    expect(wrapper.text()).toContain('No started orders with a resolvable predecessor in this period.')
    expect(wrapper.text()).toContain('No late or at-risk lots for this filter.')
    expect(wrapper.text()).toContain('No completions in this period.')
  })
})
