import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { ProductionKpiFilterParams } from '../../types/productionKpiFilterParams'
import type {
  ProductionKpiEstimateAccuracyResult,
  ProductionKpiLateLotsResult,
  ProductionKpiQualityByItemResult,
  ProductionKpiSummaryResult,
  ProductionKpiUtilizationResult,
  ProductionKpiWaitingTimeResult,
  ProductionKpiWeeklyResult,
} from '../../types/productionKpiResponse'
import type { CustomerResponse } from '@/features/customers'

function makeCustomer(id: number): CustomerResponse {
  return {
    edit_version: 0,
    id,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    archived: false,
    name: 'Customer',
    legal_name: null,
    vat_id: null,
    level: 'a',
    street: null,
    city: null,
    country: null,
    postal_code: null,
    email: null,
    phone: null,
    weblink: null,
    creator_id: 1,
    creator: null,
  }
}

function emptyRatio() {
  return { value: null, numerator: 0, denominator: 0 }
}

function makeSummary(): ProductionKpiSummaryResult {
  return {
    schedule_adherence: emptyRatio(),
    on_time_delivery: emptyRatio(),
    throughput_time: { median_days: null, p90_days: null, count: 0 },
    first_pass_yield: emptyRatio(),
    scrap_ratio: emptyRatio(),
    rework_ratio: emptyRatio(),
    utilization: null,
    availability: null,
    oee: null,
  }
}

const getSummaryMock = vi.fn<(params: ProductionKpiFilterParams) => Promise<ProductionKpiSummaryResult>>()
const getWeeklyMock = vi.fn<(params: ProductionKpiFilterParams) => Promise<ProductionKpiWeeklyResult>>()
const getUtilizationMock =
  vi.fn<(params: ProductionKpiFilterParams) => Promise<ProductionKpiUtilizationResult>>()
const getEstimateAccuracyMock =
  vi.fn<(params: ProductionKpiFilterParams) => Promise<ProductionKpiEstimateAccuracyResult>>()
const getWaitingTimeMock =
  vi.fn<(params: ProductionKpiFilterParams) => Promise<ProductionKpiWaitingTimeResult>>()
const getLateLotsMock =
  vi.fn<(params: ProductionKpiFilterParams) => Promise<ProductionKpiLateLotsResult>>()
const getQualityByItemMock =
  vi.fn<(params: ProductionKpiFilterParams) => Promise<ProductionKpiQualityByItemResult>>()

vi.mock('../../api/getProductionKpiSummary', () => ({
  getProductionKpiSummary: (params: ProductionKpiFilterParams) => getSummaryMock(params),
}))
vi.mock('../../api/getProductionKpiWeekly', () => ({
  getProductionKpiWeekly: (params: ProductionKpiFilterParams) => getWeeklyMock(params),
}))
vi.mock('../../api/getProductionKpiUtilization', () => ({
  getProductionKpiUtilization: (params: ProductionKpiFilterParams) => getUtilizationMock(params),
}))
vi.mock('../../api/getProductionKpiEstimateAccuracy', () => ({
  getProductionKpiEstimateAccuracy: (params: ProductionKpiFilterParams) =>
    getEstimateAccuracyMock(params),
}))
vi.mock('../../api/getProductionKpiWaitingTime', () => ({
  getProductionKpiWaitingTime: (params: ProductionKpiFilterParams) => getWaitingTimeMock(params),
}))
vi.mock('../../api/getProductionKpiLateLots', () => ({
  getProductionKpiLateLots: (params: ProductionKpiFilterParams) => getLateLotsMock(params),
}))
vi.mock('../../api/getProductionKpiQualityByItem', () => ({
  getProductionKpiQualityByItem: (params: ProductionKpiFilterParams) => getQualityByItemMock(params),
}))

import { useProductionKpiStore } from '../productionKpiStore'

const REFERENCE = new Date(2026, 8, 23) // Wednesday 2026-09-23, inside "this_month"

beforeEach(() => {
  setActivePinia(createPinia())
  getSummaryMock.mockReset().mockResolvedValue(makeSummary())
  getWeeklyMock.mockReset().mockResolvedValue({ points: [] })
  getUtilizationMock.mockReset().mockResolvedValue({ rows: [] })
  getEstimateAccuracyMock.mockReset().mockResolvedValue({ rows: [] })
  getWaitingTimeMock.mockReset().mockResolvedValue({ rows: [] })
  getLateLotsMock.mockReset().mockResolvedValue({ rows: [] })
  getQualityByItemMock.mockReset().mockResolvedValue({ rows: [] })
})

describe('productionKpiStore filter to query mapping', () => {
  it('defaults to this_month with no scope filters', () => {
    const store = useProductionKpiStore()
    expect(store.periodPreset).toBe('this_month')
    expect(store.queryParams.date_from).toMatch(/^\d{4}-\d{2}-01$/)
    expect(store.queryParams.machine_id).toBeNull()
    expect(store.queryParams.machine_pool_id).toBeNull()
    expect(store.queryParams.project_id).toBeNull()
    expect(store.queryParams.customer_id).toBeNull()
    expect(store.hasActiveFilters).toBe(false)
  })

  it('maps a "machine:<id>" key to machine_id, leaving machine_pool_id null', () => {
    const store = useProductionKpiStore()
    store.machineOrPoolKey = 'machine:7'
    expect(store.queryParams.machine_id).toBe(7)
    expect(store.queryParams.machine_pool_id).toBeNull()
    expect(store.hasActiveFilters).toBe(true)
  })

  it('maps a "pool:<id>" key to machine_pool_id, leaving machine_id null', () => {
    const store = useProductionKpiStore()
    store.machineOrPoolKey = 'pool:3'
    expect(store.queryParams.machine_pool_id).toBe(3)
    expect(store.queryParams.machine_id).toBeNull()
  })

  it('maps the selected project and customer to their ids', () => {
    const store = useProductionKpiStore()
    store.selectedProject = { id: 42, project_number: 'P-42', customer: null, description: null }
    store.selectedCustomer = makeCustomer(9)
    expect(store.queryParams.project_id).toBe(42)
    expect(store.queryParams.customer_id).toBe(9)
  })

  it('clearFilters resets every filter back to its default', () => {
    const store = useProductionKpiStore()
    store.machineOrPoolKey = 'machine:7'
    store.selectedProject = { id: 42, project_number: 'P-42', customer: null, description: null }
    store.periodPreset = 'last_week'

    store.clearFilters()

    expect(store.hasActiveFilters).toBe(false)
    expect(store.queryParams.machine_id).toBeNull()
    expect(store.queryParams.project_id).toBeNull()
    expect(store.periodPreset).toBe('this_month')
  })
})

describe('productionKpiStore previous-period computation', () => {
  it('shifts date_from/date_to back by the current period length, keeping scope filters', () => {
    const store = useProductionKpiStore()
    store.periodPreset = 'custom'
    store.customRange = [REFERENCE, new Date(2026, 8, 29)] // Sep 23 - Sep 29, 7 days
    store.machineOrPoolKey = 'machine:7'

    expect(store.queryParams.date_from).toBe('2026-09-23')
    expect(store.queryParams.date_to).toBe('2026-09-29')
    expect(store.previousQueryParams.date_from).toBe('2026-09-16')
    expect(store.previousQueryParams.date_to).toBe('2026-09-22')
    // The scope filters travel with the previous period unchanged.
    expect(store.previousQueryParams.machine_id).toBe(7)
  })
})

describe('productionKpiStore load', () => {
  it('fetches every endpoint, the summary twice (current and previous period), and populates results', async () => {
    const currentSummary = { ...makeSummary(), oee: 0.5 }
    const previousSummary = { ...makeSummary(), oee: 0.4 }
    getSummaryMock
      .mockResolvedValueOnce(currentSummary)
      .mockResolvedValueOnce(previousSummary)

    const store = useProductionKpiStore()
    await store.load()

    expect(getSummaryMock).toHaveBeenCalledTimes(2)
    expect(getSummaryMock).toHaveBeenNthCalledWith(1, store.queryParams)
    expect(getSummaryMock).toHaveBeenNthCalledWith(2, store.previousQueryParams)
    expect(getWeeklyMock).toHaveBeenCalledWith(store.queryParams)
    expect(getUtilizationMock).toHaveBeenCalledWith(store.queryParams)
    expect(getEstimateAccuracyMock).toHaveBeenCalledWith(store.queryParams)
    expect(getWaitingTimeMock).toHaveBeenCalledWith(store.queryParams)
    expect(getLateLotsMock).toHaveBeenCalledWith(store.queryParams)
    expect(getQualityByItemMock).toHaveBeenCalledWith(store.queryParams)

    expect(store.summary).toEqual(currentSummary)
    expect(store.previousSummary).toEqual(previousSummary)
    expect(store.loading).toBe(false)
  })
})
