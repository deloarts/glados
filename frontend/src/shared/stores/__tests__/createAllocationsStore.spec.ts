import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { createAllocationsStore } from '../createAllocationsStore'

interface TestSummary {
  allocated: number
}
interface TestAllocation {
  id: number
}

function makeApi() {
  return {
    getSummaryBatch: vi.fn<(ids: number[]) => Promise<Record<number, TestSummary>>>(),
    autoAllocate: vi.fn<(id: number) => Promise<{ ok: true }>>(),
    fulfillFromStock: vi.fn<(id: number, qty: number) => Promise<{ ok: true }>>(),
    getAllocationsForDemand: vi.fn<(id: number) => Promise<TestAllocation[]>>(),
    createAllocation: vi.fn<(payload: { demand_item_id: number }) => Promise<unknown>>(),
    updateAllocation: vi.fn<(id: number, orderItemId: number, qty: number) => Promise<unknown>>(),
    deleteAllocation: vi.fn<(id: number, orderItemId: number) => Promise<void>>(),
    updateStockAllocation: vi.fn<(id: number, qty: number) => Promise<unknown>>(),
    deleteStockAllocation: vi.fn<(id: number) => Promise<void>>(),
  }
}

describe('createAllocationsStore', () => {
  let api: ReturnType<typeof makeApi>

  beforeEach(() => {
    setActivePinia(createPinia())
    api = makeApi()
  })

  it('fetchSummaries merges the batch result into state and toggles loading', async () => {
    api.getSummaryBatch.mockResolvedValue({ 1: { allocated: 5 } })
    const store = createAllocationsStore('testAlloc1', api)()

    const promise = store.fetchSummaries([1])
    expect(store.loadingSummaries).toBe(true)
    await promise

    expect(store.loadingSummaries).toBe(false)
    expect(store.getSummary(1)).toEqual({ allocated: 5 })
  })

  it('fetchSummaries with an empty id list is a no-op', async () => {
    const store = createAllocationsStore('testAlloc2', api)()
    await store.fetchSummaries([])
    expect(api.getSummaryBatch).not.toHaveBeenCalled()
  })

  it('autoAllocate tracks in-flight demand ids and refreshes that summary after', async () => {
    api.autoAllocate.mockResolvedValue({ ok: true })
    api.getSummaryBatch.mockResolvedValue({ 1: { allocated: 3 } })
    const store = createAllocationsStore('testAlloc3', api)()

    const promise = store.autoAllocate(1)
    expect(store.isAutoAllocating(1)).toBe(true)
    await promise

    expect(store.isAutoAllocating(1)).toBe(false)
    expect(api.getSummaryBatch).toHaveBeenCalledWith([1])
  })

  it('createAllocation refetches both allocations and the summary for its demand_item_id', async () => {
    api.createAllocation.mockResolvedValue({})
    api.getAllocationsForDemand.mockResolvedValue([{ id: 9 }])
    api.getSummaryBatch.mockResolvedValue({ 7: { allocated: 1 } })
    const store = createAllocationsStore('testAlloc4', api)()

    const payload = { demand_item_id: 7, order_item_id: 1, quantity: 1 }
    await store.createAllocation(payload)

    expect(api.getAllocationsForDemand).toHaveBeenCalledWith(7)
    expect(api.getSummaryBatch).toHaveBeenCalledWith([7])
    expect(store.getAllocations(7)).toEqual([{ id: 9 }])
  })

  it('clear empties summaries and allocations but keeps in-flight tracking sets intact', () => {
    const store = createAllocationsStore('testAlloc5', api)()
    store.clear()
    expect(store.summaries).toEqual({})
    expect(store.allocations).toEqual({})
  })

  it('getAllocations/getSummary return sensible defaults for an unknown demand', () => {
    const store = createAllocationsStore('testAlloc6', api)()
    expect(store.getAllocations(999)).toEqual([])
    expect(store.getSummary(999)).toBeUndefined()
  })
})
