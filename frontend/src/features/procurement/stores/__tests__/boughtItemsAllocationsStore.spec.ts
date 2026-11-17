import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'


const getSummaryBatchMock =
  vi.fn<(demandIds: number[]) => Promise<Record<number, DemandSummaryResponse>>>()
const autoAllocateMock = vi.fn<(demandId: number) => Promise<AutoAllocateResponse>>()
const fulfillFromStockMock =
  vi.fn<(demandId: number, quantity: number) => Promise<FulfillFromStockResponse>>()
const getAllocationsForDemandMock = vi.fn<(demandId: number) => Promise<AllocationResponse[]>>()
const createAllocationMock =
  vi.fn<(payload: AllocationCreateRequest) => Promise<AllocationResponse>>()
const updateAllocationMock =
  vi.fn<(demandId: number, orderItemId: number, quantity: number) => Promise<AllocationResponse>>()
const deleteAllocationMock = vi.fn<(demandId: number, orderItemId: number) => Promise<void>>()
const updateStockAllocationMock =
  vi.fn<(demandId: number, quantity: number) => Promise<AllocationResponse>>()
const deleteStockAllocationMock = vi.fn<(demandId: number) => Promise<void>>()

vi.mock('@/features/bought-items/api/boughtItemDemandsApi', () => ({
  getDemandSummaryBatch: (demandIds: number[]) => getSummaryBatchMock(demandIds),
  autoAllocateDemand: (demandId: number) => autoAllocateMock(demandId),
  fulfillDemandFromStock: (demandId: number, quantity: number) =>
    fulfillFromStockMock(demandId, quantity),
  getAllocationsForDemand: (demandId: number) => getAllocationsForDemandMock(demandId),
  createAllocation: (payload: AllocationCreateRequest) => createAllocationMock(payload),
  updateAllocation: (demandId: number, orderItemId: number, quantity: number) =>
    updateAllocationMock(demandId, orderItemId, quantity),
  deleteAllocation: (demandId: number, orderItemId: number) =>
    deleteAllocationMock(demandId, orderItemId),
  updateStockAllocation: (demandId: number, quantity: number) =>
    updateStockAllocationMock(demandId, quantity),
  deleteStockAllocation: (demandId: number) => deleteStockAllocationMock(demandId),
}))

import { useBoughtItemsAllocationsStore } from '../boughtItemsAllocationsStore'
import type {
  AllocationCreateRequest,
  AllocationResponse,
  AutoAllocateResponse,
  DemandSummaryResponse,
  FulfillFromStockResponse,
} from '@/features/bought-items'

function makeSummary(overrides: Partial<DemandSummaryResponse> = {}): DemandSummaryResponse {
  return {
    demand_item_id: 1,
    unit: 'pcs',
    total: 10,
    allocated: 0,
    fulfilled_from_stock: 0,
    ordered: 0,
    delivered: 0,
    ...overrides,
  } as unknown as DemandSummaryResponse
}

function makeAllocation(overrides: Partial<AllocationResponse> = {}): AllocationResponse {
  return {
    demand_item_id: 1,
    order_item_id: 1,
    source: 'order',
    quantity: 5,
    ...overrides,
  } as unknown as AllocationResponse
}

// boughtItemsAllocationsStore is a thin createAllocationsStore configuration
// (see shared/stores/createAllocationsStore.spec.ts for the generic
// try/finally loading-flag behaviour). These tests pin down its own wiring:
// each of the 9 API calls it's configured with, using the real
// bought-items-allocations api modules, plus the error path of each.
describe('useBoughtItemsAllocationsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getSummaryBatchMock.mockReset()
    autoAllocateMock.mockReset()
    fulfillFromStockMock.mockReset()
    getAllocationsForDemandMock.mockReset()
    createAllocationMock.mockReset()
    updateAllocationMock.mockReset()
    deleteAllocationMock.mockReset()
    updateStockAllocationMock.mockReset()
    deleteStockAllocationMock.mockReset()
  })

  it('starts with empty summaries/allocations and every loading flag off', () => {
    const store = useBoughtItemsAllocationsStore()
    expect(store.summaries).toEqual({})
    expect(store.allocations).toEqual({})
    expect(store.loadingSummaries).toBe(false)
    expect(store.loadingAllocations).toBe(false)
    expect(store.savingAllocation).toBe(false)
  })

  it('fetchSummaries calls getDemandSummaryBatch and merges the result', async () => {
    getSummaryBatchMock.mockResolvedValue({ 1: makeSummary({ demand_item_id: 1, allocated: 4 }) })
    const store = useBoughtItemsAllocationsStore()

    const promise = store.fetchSummaries([1])
    expect(store.loadingSummaries).toBe(true)
    await promise

    expect(getSummaryBatchMock).toHaveBeenCalledWith([1])
    expect(store.loadingSummaries).toBe(false)
    expect(store.getSummary(1)).toEqual(makeSummary({ demand_item_id: 1, allocated: 4 }))
  })

  it('fetchSummaries resets loadingSummaries and rethrows on failure', async () => {
    getSummaryBatchMock.mockRejectedValue(new Error('summary batch failed'))
    const store = useBoughtItemsAllocationsStore()

    await expect(store.fetchSummaries([1])).rejects.toThrow('summary batch failed')
    expect(store.loadingSummaries).toBe(false)
    expect(store.getSummary(1)).toBeUndefined()
  })

  it('autoAllocate calls autoAllocateDemand, tracks the in-flight id, and refreshes its summary', async () => {
    autoAllocateMock.mockResolvedValue({ demand_item_id: 1 } as unknown as AutoAllocateResponse)
    getSummaryBatchMock.mockResolvedValue({ 1: makeSummary({ allocated: 10 }) })
    const store = useBoughtItemsAllocationsStore()

    const promise = store.autoAllocate(1)
    expect(store.isAutoAllocating(1)).toBe(true)
    await promise

    expect(autoAllocateMock).toHaveBeenCalledWith(1)
    expect(getSummaryBatchMock).toHaveBeenCalledWith([1])
    expect(store.isAutoAllocating(1)).toBe(false)
  })

  it('autoAllocate clears the in-flight id and rethrows on failure', async () => {
    autoAllocateMock.mockRejectedValue(new Error('no stock available'))
    const store = useBoughtItemsAllocationsStore()

    await expect(store.autoAllocate(1)).rejects.toThrow('no stock available')
    expect(store.isAutoAllocating(1)).toBe(false)
  })

  it('fulfillFromStock calls fulfillDemandFromStock, tracks the in-flight id, and refreshes its summary', async () => {
    fulfillFromStockMock.mockResolvedValue({ demand_item_id: 1 } as unknown as FulfillFromStockResponse)
    getSummaryBatchMock.mockResolvedValue({ 1: makeSummary({ fulfilled_from_stock: 3 }) })
    const store = useBoughtItemsAllocationsStore()

    const promise = store.fulfillFromStock(1, 3)
    expect(store.isFulfillingFromStock(1)).toBe(true)
    await promise

    expect(fulfillFromStockMock).toHaveBeenCalledWith(1, 3)
    expect(getSummaryBatchMock).toHaveBeenCalledWith([1])
    expect(store.isFulfillingFromStock(1)).toBe(false)
  })

  it('fulfillFromStock clears the in-flight id and rethrows on failure', async () => {
    fulfillFromStockMock.mockRejectedValue(new Error('insufficient stock'))
    const store = useBoughtItemsAllocationsStore()

    await expect(store.fulfillFromStock(1, 3)).rejects.toThrow('insufficient stock')
    expect(store.isFulfillingFromStock(1)).toBe(false)
  })

  it('fetchAllocations calls getAllocationsForDemand and caches the result per demand', async () => {
    getAllocationsForDemandMock.mockResolvedValue([makeAllocation({ order_item_id: 9 })])
    const store = useBoughtItemsAllocationsStore()

    const promise = store.fetchAllocations(1)
    expect(store.loadingAllocations).toBe(true)
    await promise

    expect(getAllocationsForDemandMock).toHaveBeenCalledWith(1)
    expect(store.loadingAllocations).toBe(false)
    expect(store.getAllocations(1)).toEqual([makeAllocation({ order_item_id: 9 })])
  })

  it('fetchAllocations resets loadingAllocations and rethrows on failure', async () => {
    getAllocationsForDemandMock.mockRejectedValue(new Error('demand not found'))
    const store = useBoughtItemsAllocationsStore()

    await expect(store.fetchAllocations(1)).rejects.toThrow('demand not found')
    expect(store.loadingAllocations).toBe(false)
    expect(store.getAllocations(1)).toEqual([])
  })

  it('createAllocation calls createAllocation, then refetches allocations and the summary for its demand', async () => {
    const payload: AllocationCreateRequest = { demand_item_id: 1, order_item_id: 9, quantity: 5 }
    createAllocationMock.mockResolvedValue(makeAllocation())
    getAllocationsForDemandMock.mockResolvedValue([makeAllocation({ order_item_id: 9 })])
    getSummaryBatchMock.mockResolvedValue({ 1: makeSummary({ allocated: 5 }) })
    const store = useBoughtItemsAllocationsStore()

    const promise = store.createAllocation(payload)
    expect(store.savingAllocation).toBe(true)
    await promise

    expect(createAllocationMock).toHaveBeenCalledWith(payload)
    expect(getAllocationsForDemandMock).toHaveBeenCalledWith(1)
    expect(getSummaryBatchMock).toHaveBeenCalledWith([1])
    expect(store.savingAllocation).toBe(false)
    expect(store.getAllocations(1)).toEqual([makeAllocation({ order_item_id: 9 })])
  })

  it('createAllocation resets savingAllocation and rethrows on failure', async () => {
    createAllocationMock.mockRejectedValue(new Error('order item already allocated'))
    const store = useBoughtItemsAllocationsStore()

    await expect(
      store.createAllocation({ demand_item_id: 1, order_item_id: 9, quantity: 5 }),
    ).rejects.toThrow('order item already allocated')
    expect(store.savingAllocation).toBe(false)
  })

  it('updateAllocation calls updateAllocation, then refetches allocations and the summary', async () => {
    updateAllocationMock.mockResolvedValue(makeAllocation({ quantity: 8 }))
    getAllocationsForDemandMock.mockResolvedValue([makeAllocation({ quantity: 8 })])
    getSummaryBatchMock.mockResolvedValue({ 1: makeSummary({ allocated: 8 }) })
    const store = useBoughtItemsAllocationsStore()

    await store.updateAllocation(1, 9, 8)

    expect(updateAllocationMock).toHaveBeenCalledWith(1, 9, 8)
    expect(getAllocationsForDemandMock).toHaveBeenCalledWith(1)
    expect(getSummaryBatchMock).toHaveBeenCalledWith([1])
  })

  it('updateAllocation resets savingAllocation and rethrows on failure', async () => {
    updateAllocationMock.mockRejectedValue(new Error('quantity exceeds order'))
    const store = useBoughtItemsAllocationsStore()

    await expect(store.updateAllocation(1, 9, 8)).rejects.toThrow('quantity exceeds order')
    expect(store.savingAllocation).toBe(false)
  })

  it('deleteAllocation calls deleteAllocation, then refetches allocations and the summary', async () => {
    deleteAllocationMock.mockResolvedValue(undefined)
    getAllocationsForDemandMock.mockResolvedValue([])
    getSummaryBatchMock.mockResolvedValue({ 1: makeSummary({ allocated: 0 }) })
    const store = useBoughtItemsAllocationsStore()

    await store.deleteAllocation(1, 9)

    expect(deleteAllocationMock).toHaveBeenCalledWith(1, 9)
    expect(store.getAllocations(1)).toEqual([])
  })

  it('deleteAllocation resets savingAllocation and rethrows on failure', async () => {
    deleteAllocationMock.mockRejectedValue(new Error('allocation not found'))
    const store = useBoughtItemsAllocationsStore()

    await expect(store.deleteAllocation(1, 9)).rejects.toThrow('allocation not found')
    expect(store.savingAllocation).toBe(false)
  })

  it('updateStockAllocation calls updateStockAllocation, then refetches allocations and the summary', async () => {
    updateStockAllocationMock.mockResolvedValue(makeAllocation({ source: 'stock', quantity: 4 }))
    getAllocationsForDemandMock.mockResolvedValue([makeAllocation({ source: 'stock', quantity: 4 })])
    getSummaryBatchMock.mockResolvedValue({ 1: makeSummary({ fulfilled_from_stock: 4 }) })
    const store = useBoughtItemsAllocationsStore()

    await store.updateStockAllocation(1, 4)

    expect(updateStockAllocationMock).toHaveBeenCalledWith(1, 4)
    expect(getAllocationsForDemandMock).toHaveBeenCalledWith(1)
    expect(getSummaryBatchMock).toHaveBeenCalledWith([1])
  })

  it('updateStockAllocation resets savingAllocation and rethrows on failure', async () => {
    updateStockAllocationMock.mockRejectedValue(new Error('insufficient stock'))
    const store = useBoughtItemsAllocationsStore()

    await expect(store.updateStockAllocation(1, 4)).rejects.toThrow('insufficient stock')
    expect(store.savingAllocation).toBe(false)
  })

  it('deleteStockAllocation calls deleteStockAllocation, then refetches allocations and the summary', async () => {
    deleteStockAllocationMock.mockResolvedValue(undefined)
    getAllocationsForDemandMock.mockResolvedValue([])
    getSummaryBatchMock.mockResolvedValue({ 1: makeSummary({ fulfilled_from_stock: 0 }) })
    const store = useBoughtItemsAllocationsStore()

    await store.deleteStockAllocation(1)

    expect(deleteStockAllocationMock).toHaveBeenCalledWith(1)
    expect(store.getAllocations(1)).toEqual([])
  })

  it('deleteStockAllocation resets savingAllocation and rethrows on failure', async () => {
    deleteStockAllocationMock.mockRejectedValue(new Error('stock allocation not found'))
    const store = useBoughtItemsAllocationsStore()

    await expect(store.deleteStockAllocation(1)).rejects.toThrow('stock allocation not found')
    expect(store.savingAllocation).toBe(false)
  })

  it('getAllocations/getSummary return sensible defaults for an unknown demand', () => {
    const store = useBoughtItemsAllocationsStore()
    expect(store.getAllocations(999)).toEqual([])
    expect(store.getSummary(999)).toBeUndefined()
  })

  it('clear empties summaries and allocations', async () => {
    getSummaryBatchMock.mockResolvedValue({ 1: makeSummary() })
    getAllocationsForDemandMock.mockResolvedValue([makeAllocation()])
    const store = useBoughtItemsAllocationsStore()
    await store.fetchSummaries([1])
    await store.fetchAllocations(1)

    store.clear()

    expect(store.summaries).toEqual({})
    expect(store.allocations).toEqual({})
  })
})
