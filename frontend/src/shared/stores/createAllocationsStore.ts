import { ref } from 'vue'
import { defineStore } from 'pinia'

/**
 * The 9 API calls behind a demand-allocation store, one HTTP call each,
 * named by what they do rather than mirrored 1:1 from any particular
 * feature's `api/` module names, since bought-items and source-items name
 * theirs slightly differently already.
 */
export interface AllocationsStoreApi<
  TSummary,
  TAllocation,
  TAutoAllocateResult,
  TFulfillResult,
  TCreatePayload extends { demand_item_id: number },
> {
  getSummaryBatch: (demandIds: number[]) => Promise<Record<number, TSummary>>
  autoAllocate: (demandId: number) => Promise<TAutoAllocateResult>
  fulfillFromStock: (demandId: number, quantity: number) => Promise<TFulfillResult>
  getAllocationsForDemand: (demandId: number) => Promise<TAllocation[]>
  createAllocation: (payload: TCreatePayload) => Promise<unknown>
  updateAllocation: (demandId: number, orderItemId: number, quantity: number) => Promise<unknown>
  deleteAllocation: (demandId: number, orderItemId: number) => Promise<void>
  updateStockAllocation: (demandId: number, quantity: number) => Promise<unknown>
  deleteStockAllocation: (demandId: number) => Promise<void>
}

/**
 * Demand-allocation state + actions shared by bought-items and source-items
 * (functionally identical modulo which API module backs each call), NOT
 * made-items, whose allocation model is genuinely different (no manual
 * order-item allocation, lots instead of order items), so it stays its own
 * hand-written store rather than being forced through this factory.
 */
export function createAllocationsStore<
  TSummary,
  TAllocation,
  TAutoAllocateResult,
  TFulfillResult,
  TCreatePayload extends { demand_item_id: number },
>(
  id: string,
  api: AllocationsStoreApi<
    TSummary,
    TAllocation,
    TAutoAllocateResult,
    TFulfillResult,
    TCreatePayload
  >,
) {
  return defineStore(id, () => {
    const summaries = ref<Record<number, TSummary>>({})
    const loadingSummaries = ref(false)
    const autoAllocating = ref<Set<number>>(new Set())
    const fulfillingFromStock = ref<Set<number>>(new Set())
    const allocations = ref<Record<number, TAllocation[]>>({})
    const loadingAllocations = ref(false)
    const savingAllocation = ref(false)

    async function fetchSummaries(demandIds: number[]): Promise<void> {
      if (demandIds.length === 0) return

      loadingSummaries.value = true

      try {
        const result = await api.getSummaryBatch(demandIds)
        summaries.value = { ...summaries.value, ...result }
      } finally {
        loadingSummaries.value = false
      }
    }

    async function autoAllocate(demandId: number): Promise<TAutoAllocateResult> {
      autoAllocating.value = new Set([...autoAllocating.value, demandId])

      try {
        const result = await api.autoAllocate(demandId)
        await fetchSummaries([demandId])
        return result
      } finally {
        const next = new Set(autoAllocating.value)
        next.delete(demandId)
        autoAllocating.value = next
      }
    }

    async function fulfillFromStock(demandId: number, quantity: number): Promise<TFulfillResult> {
      fulfillingFromStock.value = new Set([...fulfillingFromStock.value, demandId])

      try {
        const result = await api.fulfillFromStock(demandId, quantity)
        await fetchSummaries([demandId])
        return result
      } finally {
        const next = new Set(fulfillingFromStock.value)
        next.delete(demandId)
        fulfillingFromStock.value = next
      }
    }

    async function fetchAllocations(demandId: number): Promise<void> {
      loadingAllocations.value = true

      try {
        const result = await api.getAllocationsForDemand(demandId)
        allocations.value = { ...allocations.value, [demandId]: result }
      } finally {
        loadingAllocations.value = false
      }
    }

    async function createAllocation(payload: TCreatePayload): Promise<void> {
      savingAllocation.value = true

      try {
        await api.createAllocation(payload)
        await Promise.all([
          fetchAllocations(payload.demand_item_id),
          fetchSummaries([payload.demand_item_id]),
        ])
      } finally {
        savingAllocation.value = false
      }
    }

    async function updateAllocation(
      demandId: number,
      orderItemId: number,
      quantity: number,
    ): Promise<void> {
      savingAllocation.value = true

      try {
        await api.updateAllocation(demandId, orderItemId, quantity)
        await Promise.all([fetchAllocations(demandId), fetchSummaries([demandId])])
      } finally {
        savingAllocation.value = false
      }
    }

    async function deleteAllocation(demandId: number, orderItemId: number): Promise<void> {
      savingAllocation.value = true

      try {
        await api.deleteAllocation(demandId, orderItemId)
        await Promise.all([fetchAllocations(demandId), fetchSummaries([demandId])])
      } finally {
        savingAllocation.value = false
      }
    }

    async function updateStockAllocation(demandId: number, quantity: number): Promise<void> {
      savingAllocation.value = true

      try {
        await api.updateStockAllocation(demandId, quantity)
        await Promise.all([fetchAllocations(demandId), fetchSummaries([demandId])])
      } finally {
        savingAllocation.value = false
      }
    }

    async function deleteStockAllocation(demandId: number): Promise<void> {
      savingAllocation.value = true

      try {
        await api.deleteStockAllocation(demandId)
        await Promise.all([fetchAllocations(demandId), fetchSummaries([demandId])])
      } finally {
        savingAllocation.value = false
      }
    }

    function getAllocations(demandId: number): TAllocation[] {
      return allocations.value[demandId] ?? []
    }

    function getSummary(demandId: number): TSummary | undefined {
      return summaries.value[demandId]
    }

    function isAutoAllocating(demandId: number): boolean {
      return autoAllocating.value.has(demandId)
    }

    function isFulfillingFromStock(demandId: number): boolean {
      return fulfillingFromStock.value.has(demandId)
    }

    function clear(): void {
      summaries.value = {}
      allocations.value = {}
    }

    return {
      summaries,
      loadingSummaries,
      allocations,
      loadingAllocations,
      savingAllocation,
      fetchSummaries,
      autoAllocate,
      fulfillFromStock,
      fetchAllocations,
      createAllocation,
      updateAllocation,
      deleteAllocation,
      updateStockAllocation,
      deleteStockAllocation,
      getAllocations,
      getSummary,
      isAutoAllocating,
      isFulfillingFromStock,
      clear,
    }
  })
}
