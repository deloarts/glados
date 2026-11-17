import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { ProductionKpiFilterParams } from '../../types/productionKpiFilterParams'
import type {
  ProductionKpiRejectedPerSupplierResult,
  ProductionKpiScrapByReasonResult,
} from '../../types/productionKpiResponse'

// A sibling spec file rather than an addition to productionKpiStore.spec.ts:
// that file mocks every one of load()'s own seven api/*.ts modules by exact
// path and asserts store.load() calls exactly those, so the two scrap-kpi
// calls (which load() deliberately never triggers, see the store's own
// loadScrapKpis() docstring) would either go untested there or loosen that
// pinned assertion. Naming convention matches
// LotsTable.scrap.spec.ts / LotsTable.sourceApproval.spec.ts.
const getScrapByReasonMock =
  vi.fn<(params: ProductionKpiFilterParams) => Promise<ProductionKpiScrapByReasonResult>>()
const getRejectedPerSupplierMock =
  vi.fn<(params: ProductionKpiFilterParams) => Promise<ProductionKpiRejectedPerSupplierResult>>()

vi.mock('../../api/getProductionKpiScrapByReason', () => ({
  getProductionKpiScrapByReason: (params: ProductionKpiFilterParams) =>
    getScrapByReasonMock(params),
}))
vi.mock('../../api/getProductionKpiRejectedPerSupplier', () => ({
  getProductionKpiRejectedPerSupplier: (params: ProductionKpiFilterParams) =>
    getRejectedPerSupplierMock(params),
}))

import { useProductionKpiStore } from '../productionKpiStore'

beforeEach(() => {
  setActivePinia(createPinia())
  getScrapByReasonMock.mockReset().mockResolvedValue({ rows: [] })
  getRejectedPerSupplierMock.mockReset().mockResolvedValue({ rows: [] })
})

describe('productionKpiStore.loadScrapKpis', () => {
  it('fetches both endpoints with the current query params and populates results', async () => {
    const scrapResult: ProductionKpiScrapByReasonResult = {
      rows: [{ reason: 'tool_breakage', quantity: 3, share: { value: 1, numerator: 3, denominator: 3 } }],
    }
    const supplierResult: ProductionKpiRejectedPerSupplierResult = {
      rows: [
        {
          supplier_id: 1,
          supplier_name: 'Acme',
          delivered: 9,
          rejected: 1,
          rejected_ratio: { value: 0.1, numerator: 1, denominator: 10 },
          rejected_lost: 1,
        },
      ],
    }
    getScrapByReasonMock.mockResolvedValue(scrapResult)
    getRejectedPerSupplierMock.mockResolvedValue(supplierResult)

    const store = useProductionKpiStore()
    await store.loadScrapKpis()

    expect(getScrapByReasonMock).toHaveBeenCalledWith(store.queryParams)
    expect(getRejectedPerSupplierMock).toHaveBeenCalledWith(store.queryParams)
    expect(store.scrapByReason).toEqual(scrapResult)
    expect(store.rejectedPerSupplier).toEqual(supplierResult)
    expect(store.scrapLoading).toBe(false)
    expect(store.scrapError).toBeNull()
  })

  it('leaves both results null when one of the two calls fails', async () => {
    getScrapByReasonMock.mockRejectedValue(new Error('network error'))

    const store = useProductionKpiStore()
    await store.loadScrapKpis()

    // Promise.all rejects as a whole, so a failure on either endpoint
    // leaves both refs at their initial null rather than partially
    // populated from just the one call that did resolve.
    expect(store.scrapByReason).toBeNull()
    expect(store.rejectedPerSupplier).toBeNull()
    expect(store.scrapLoading).toBe(false)
  })

  it('reflects the current queryParams (scope filters included) on each call', async () => {
    const store = useProductionKpiStore()
    store.machineOrPoolKey = 'machine:7'

    await store.loadScrapKpis()

    expect(getScrapByReasonMock).toHaveBeenCalledWith(
      expect.objectContaining({ machine_id: 7 }),
    )
    expect(getRejectedPerSupplierMock).toHaveBeenCalledWith(
      expect.objectContaining({ machine_id: 7 }),
    )
  })
})
