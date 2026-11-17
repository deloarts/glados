import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'


const getSummaryBatchMock =
  vi.fn<(demandIds: number[]) => Promise<Record<number, MadeItemDemandSummaryResponse>>>()
const fulfillFromStockMock =
  vi.fn<(demandId: number, quantity: number) => Promise<MadeItemFulfillFromStockResponse>>()
const getAllocationsMock = vi.fn<(demandId: number) => Promise<MadeItemAllocationResponse[]>>()
const updateStockMock =
  vi.fn<(demandId: number, quantity: number) => Promise<MadeItemAllocationResponse>>()
const deleteStockMock = vi.fn<(demandId: number) => Promise<void>>()

vi.mock('@/features/made-items/api/madeItemDemandsApi', () => ({
  getMadeItemDemandSummaryBatch: (demandIds: number[]) => getSummaryBatchMock(demandIds),
  fulfillMadeItemDemandFromStock: (demandId: number, quantity: number) =>
    fulfillFromStockMock(demandId, quantity),
  getMadeItemAllocationsForDemand: (demandId: number) => getAllocationsMock(demandId),
  updateMadeItemStockAllocation: (demandId: number, quantity: number) =>
    updateStockMock(demandId, quantity),
  deleteMadeItemStockAllocation: (demandId: number) => deleteStockMock(demandId),
}))

import { useMadeItemsAllocationsStore } from '../madeItemsAllocationsStore'
import type {
  MadeItemAllocationResponse,
  MadeItemDemandSummaryResponse,
  MadeItemFulfillFromStockResponse,
} from '@/features/made-items'

function makeSummary(overrides: Partial<MadeItemDemandSummaryResponse> = {}): MadeItemDemandSummaryResponse {
  return {
    demand_item_id: 1,
    unit: 'PCS',
    total: 10,
    allocated: 4,
    fulfilled_from_stock: 2,
    ordered: 0,
    delivered: 0,
    remaining: 6,
    unallocated: 6,
    pending: 0,
    in_transit: 0,
    is_fully_allocated: false,
    is_fully_delivered: false,
    lot_ids: [],
    ...overrides,
  }
}

function makeAllocation(overrides: Partial<MadeItemAllocationResponse> = {}): MadeItemAllocationResponse {
  return {
    demand_item_id: 1,
    lot_id: 1,
    source: 'lot',
    quantity: 2,
    ...overrides,
  }
}

function makeFulfillResponse(
  overrides: Partial<MadeItemFulfillFromStockResponse> = {},
): MadeItemFulfillFromStockResponse {
  return {
    demand_item_id: 1,
    quantity_fulfilled: 2,
    total_fulfilled_from_stock: 2,
    remaining_unallocated: 4,
    demand_status_changed_to: null,
    ...overrides,
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('useMadeItemsAllocationsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getSummaryBatchMock.mockReset()
    fulfillFromStockMock.mockReset()
    getAllocationsMock.mockReset()
    updateStockMock.mockReset()
    deleteStockMock.mockReset()
  })

  it('starts empty: no summaries, no allocations, and every flag off', () => {
    const store = useMadeItemsAllocationsStore()
    expect(store.summaries).toEqual({})
    expect(store.loadingSummaries).toBe(false)
    expect(store.allocations).toEqual({})
    expect(store.loadingAllocations).toBe(false)
    expect(store.savingAllocation).toBe(false)
    expect(store.getSummary(1)).toBeUndefined()
    expect(store.getAllocations(1)).toEqual([])
    expect(store.isFulfillingFromStock(1)).toBe(false)
  })

  describe('fetchSummaries', () => {
    it('fetches a batch and merges it into summaries, keyed by demand id', async () => {
      getSummaryBatchMock.mockResolvedValue({ 1: makeSummary({ demand_item_id: 1 }) })
      const store = useMadeItemsAllocationsStore()

      await store.fetchSummaries([1])

      expect(getSummaryBatchMock).toHaveBeenCalledWith([1])
      expect(store.getSummary(1)?.demand_item_id).toBe(1)
      expect(store.loadingSummaries).toBe(false)
    })

    it('merges into existing summaries rather than replacing the whole map', async () => {
      getSummaryBatchMock.mockResolvedValueOnce({ 1: makeSummary({ demand_item_id: 1 }) })
      const store = useMadeItemsAllocationsStore()
      await store.fetchSummaries([1])

      getSummaryBatchMock.mockResolvedValueOnce({ 2: makeSummary({ demand_item_id: 2 }) })
      await store.fetchSummaries([2])

      expect(store.getSummary(1)?.demand_item_id).toBe(1)
      expect(store.getSummary(2)?.demand_item_id).toBe(2)
    })

    it('is a no-op for an empty id list', async () => {
      const store = useMadeItemsAllocationsStore()

      await store.fetchSummaries([])

      expect(getSummaryBatchMock).not.toHaveBeenCalled()
    })

    it('sets loadingSummaries while the request is in flight', async () => {
      const { promise, resolve } = deferred<Record<number, MadeItemDemandSummaryResponse>>()
      getSummaryBatchMock.mockReturnValue(promise)
      const store = useMadeItemsAllocationsStore()

      const call = store.fetchSummaries([1])
      expect(store.loadingSummaries).toBe(true)

      resolve({ 1: makeSummary() })
      await call
      expect(store.loadingSummaries).toBe(false)
    })

    it('resets loadingSummaries and propagates the error on failure', async () => {
      getSummaryBatchMock.mockRejectedValueOnce(new Error('network error'))
      const store = useMadeItemsAllocationsStore()

      await expect(store.fetchSummaries([1])).rejects.toThrow('network error')

      expect(store.loadingSummaries).toBe(false)
      expect(store.getSummary(1)).toBeUndefined()
    })
  })

  describe('fetchAllocations', () => {
    it('fetches and stores allocations for a demand', async () => {
      const rows = [makeAllocation({ lot_id: 1 }), makeAllocation({ lot_id: 2 })]
      getAllocationsMock.mockResolvedValue(rows)
      const store = useMadeItemsAllocationsStore()

      await store.fetchAllocations(5)

      expect(getAllocationsMock).toHaveBeenCalledWith(5)
      expect(store.getAllocations(5)).toEqual(rows)
      expect(store.loadingAllocations).toBe(false)
    })

    it('resets loadingAllocations and propagates the error on failure', async () => {
      getAllocationsMock.mockRejectedValueOnce(new Error('network error'))
      const store = useMadeItemsAllocationsStore()

      await expect(store.fetchAllocations(5)).rejects.toThrow('network error')

      expect(store.loadingAllocations).toBe(false)
      expect(store.getAllocations(5)).toEqual([])
    })
  })

  describe('fulfillFromStock', () => {
    it('fulfills from stock, then refreshes allocations and the summary for that demand', async () => {
      fulfillFromStockMock.mockResolvedValue(makeFulfillResponse({ demand_item_id: 3 }))
      getAllocationsMock.mockResolvedValue([makeAllocation({ demand_item_id: 3 })])
      getSummaryBatchMock.mockResolvedValue({ 3: makeSummary({ demand_item_id: 3 }) })
      const store = useMadeItemsAllocationsStore()

      const result = await store.fulfillFromStock(3, 2)

      expect(fulfillFromStockMock).toHaveBeenCalledWith(3, 2)
      expect(result.demand_item_id).toBe(3)
      expect(getAllocationsMock).toHaveBeenCalledWith(3)
      expect(getSummaryBatchMock).toHaveBeenCalledWith([3])
      expect(store.getAllocations(3)).toHaveLength(1)
      expect(store.getSummary(3)?.demand_item_id).toBe(3)
    })

    it('marks the demand as fulfilling while in flight, independently of other demands', async () => {
      const first = deferred<MadeItemFulfillFromStockResponse>()
      fulfillFromStockMock.mockReturnValueOnce(first.promise)
      const store = useMadeItemsAllocationsStore()

      const call = store.fulfillFromStock(1, 2)
      expect(store.isFulfillingFromStock(1)).toBe(true)
      expect(store.isFulfillingFromStock(2)).toBe(false)

      getAllocationsMock.mockResolvedValue([])
      getSummaryBatchMock.mockResolvedValue({})
      first.resolve(makeFulfillResponse({ demand_item_id: 1 }))
      await call

      expect(store.isFulfillingFromStock(1)).toBe(false)
    })

    it('clears the fulfilling flag and propagates the error on failure, without refreshing', async () => {
      fulfillFromStockMock.mockRejectedValueOnce(new Error('insufficient stock'))
      const store = useMadeItemsAllocationsStore()

      await expect(store.fulfillFromStock(1, 2)).rejects.toThrow('insufficient stock')

      expect(store.isFulfillingFromStock(1)).toBe(false)
      expect(getAllocationsMock).not.toHaveBeenCalled()
      expect(getSummaryBatchMock).not.toHaveBeenCalled()
    })
  })

  describe('updateStockAllocation', () => {
    it('updates the stock allocation, then refreshes allocations and the summary', async () => {
      updateStockMock.mockResolvedValue(makeAllocation({ demand_item_id: 4, quantity: 9 }))
      getAllocationsMock.mockResolvedValue([makeAllocation({ demand_item_id: 4, quantity: 9 })])
      getSummaryBatchMock.mockResolvedValue({ 4: makeSummary({ demand_item_id: 4 }) })
      const store = useMadeItemsAllocationsStore()

      await store.updateStockAllocation(4, 9)

      expect(updateStockMock).toHaveBeenCalledWith(4, 9)
      expect(getAllocationsMock).toHaveBeenCalledWith(4)
      expect(getSummaryBatchMock).toHaveBeenCalledWith([4])
      expect(store.getAllocations(4)?.[0]?.quantity).toBe(9)
    })

    it('toggles savingAllocation while in flight', async () => {
      const { promise, resolve } = deferred<MadeItemAllocationResponse>()
      updateStockMock.mockReturnValue(promise)
      const store = useMadeItemsAllocationsStore()

      const call = store.updateStockAllocation(4, 9)
      expect(store.savingAllocation).toBe(true)

      getAllocationsMock.mockResolvedValue([])
      getSummaryBatchMock.mockResolvedValue({})
      resolve(makeAllocation())
      await call

      expect(store.savingAllocation).toBe(false)
    })

    it('resets savingAllocation and propagates the error on failure, without refreshing', async () => {
      updateStockMock.mockRejectedValueOnce(new Error('conflict'))
      const store = useMadeItemsAllocationsStore()

      await expect(store.updateStockAllocation(4, 9)).rejects.toThrow('conflict')

      expect(store.savingAllocation).toBe(false)
      expect(getAllocationsMock).not.toHaveBeenCalled()
    })
  })

  describe('deleteStockAllocation', () => {
    it('deletes the stock allocation, then refreshes allocations and the summary', async () => {
      deleteStockMock.mockResolvedValue(undefined)
      getAllocationsMock.mockResolvedValue([])
      getSummaryBatchMock.mockResolvedValue({ 4: makeSummary({ demand_item_id: 4, allocated: 0 }) })
      const store = useMadeItemsAllocationsStore()

      await store.deleteStockAllocation(4)

      expect(deleteStockMock).toHaveBeenCalledWith(4)
      expect(getAllocationsMock).toHaveBeenCalledWith(4)
      expect(getSummaryBatchMock).toHaveBeenCalledWith([4])
      expect(store.getAllocations(4)).toEqual([])
    })

    it('resets savingAllocation and propagates the error on failure, without refreshing', async () => {
      deleteStockMock.mockRejectedValueOnce(new Error('not found'))
      const store = useMadeItemsAllocationsStore()

      await expect(store.deleteStockAllocation(4)).rejects.toThrow('not found')

      expect(store.savingAllocation).toBe(false)
      expect(getAllocationsMock).not.toHaveBeenCalled()
    })
  })

  describe('clear', () => {
    it('empties summaries and allocations', async () => {
      getSummaryBatchMock.mockResolvedValue({ 1: makeSummary() })
      getAllocationsMock.mockResolvedValue([makeAllocation()])
      const store = useMadeItemsAllocationsStore()
      await store.fetchSummaries([1])
      await store.fetchAllocations(1)

      store.clear()

      expect(store.summaries).toEqual({})
      expect(store.allocations).toEqual({})
    })
  })
})
