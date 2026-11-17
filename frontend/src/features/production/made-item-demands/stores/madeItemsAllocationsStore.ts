import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  getMadeItemDemandSummaryBatch,
  fulfillMadeItemDemandFromStock,
  getMadeItemAllocationsForDemand,
  updateMadeItemStockAllocation as updateMadeItemStockAllocationRequest,
  deleteMadeItemStockAllocation as deleteMadeItemStockAllocationRequest,
} from '@/features/made-items'
import type {
  MadeItemAllocationResponse,
  MadeItemDemandSummaryResponse,
  MadeItemFulfillFromStockResponse,
} from '@/features/made-items'



export const useMadeItemsAllocationsStore = defineStore('madeItemsAllocations', () => {
  const summaries = ref<Record<number, MadeItemDemandSummaryResponse>>({})
  const loadingSummaries = ref(false)
  const fulfillingFromStock = ref<Set<number>>(new Set())
  const allocations = ref<Record<number, MadeItemAllocationResponse[]>>({})
  const loadingAllocations = ref(false)
  const savingAllocation = ref(false)

  async function fetchSummaries(demandIds: number[]): Promise<void> {
    if (demandIds.length === 0) return

    loadingSummaries.value = true

    try {
      const result = await getMadeItemDemandSummaryBatch(demandIds)
      summaries.value = { ...summaries.value, ...result }
    } finally {
      loadingSummaries.value = false
    }
  }

  async function fulfillFromStock(
    demandId: number,
    quantity: number,
  ): Promise<MadeItemFulfillFromStockResponse> {
    fulfillingFromStock.value = new Set([...fulfillingFromStock.value, demandId])

    try {
      const result = await fulfillMadeItemDemandFromStock(demandId, quantity)
      await Promise.all([fetchAllocations(demandId), fetchSummaries([demandId])])
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
      const result = await getMadeItemAllocationsForDemand(demandId)
      allocations.value = { ...allocations.value, [demandId]: result }
    } finally {
      loadingAllocations.value = false
    }
  }

  async function updateStockAllocation(demandId: number, quantity: number): Promise<void> {
    savingAllocation.value = true

    try {
      await updateMadeItemStockAllocationRequest(demandId, quantity)
      await Promise.all([fetchAllocations(demandId), fetchSummaries([demandId])])
    } finally {
      savingAllocation.value = false
    }
  }

  async function deleteStockAllocation(demandId: number): Promise<void> {
    savingAllocation.value = true

    try {
      await deleteMadeItemStockAllocationRequest(demandId)
      await Promise.all([fetchAllocations(demandId), fetchSummaries([demandId])])
    } finally {
      savingAllocation.value = false
    }
  }

  function getAllocations(demandId: number): MadeItemAllocationResponse[] {
    return allocations.value[demandId] ?? []
  }

  function getSummary(demandId: number): MadeItemDemandSummaryResponse | undefined {
    return summaries.value[demandId]
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
    fulfillFromStock,
    fetchAllocations,
    updateStockAllocation,
    deleteStockAllocation,
    getAllocations,
    getSummary,
    isFulfillingFromStock,
    clear,
  }
})
