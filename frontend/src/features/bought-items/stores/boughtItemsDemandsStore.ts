import { ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import {
  createDemand,
  getDemands,
  updateDemand,
  updateDemandStatus,
  cancelDemand,
  setDemandBucket,
} from '../api/boughtItemDemandsApi'
import { deleteBoughtItemDemand } from '../api/deleteBoughtItemDemand'

import type {
  DemandItemCreateRequest,
  DemandItemFilterParams,
  DemandItemUpdateRequest,
} from '../types/boughtItemsDemandsRequest'
import type { BoughtItemDemandResponse, BoughtItemDemandStatus } from '../types/boughtItemsDemandsResponse'

export const useBoughtItemsDemandsStore = defineStore('boughtItemsDemands', () => {
  const { loading, error, run } = useSequencedFetch(getDemands)
  const items = ref<BoughtItemDemandResponse[]>([])
  const total = ref(0)
  const refreshTrigger = ref(0)

  async function refresh(params?: DemandItemFilterParams): Promise<void> {
    const response = await run(params)
    if (!response) return

    items.value = response.items
    total.value = response.total
  }

  function triggerRefresh(): void {
    refreshTrigger.value++
  }

  function clear(): void {
    items.value = []
    total.value = 0
  }

  async function create(payload: DemandItemCreateRequest): Promise<BoughtItemDemandResponse> {
    return await createDemand(payload)
  }

  async function update(id: number, payload: DemandItemUpdateRequest): Promise<BoughtItemDemandResponse> {
    const updated = await updateDemand(id, payload)
    replaceItem(updated)
    return updated
  }

  async function updateStatus(id: number, newStatus: BoughtItemDemandStatus): Promise<BoughtItemDemandResponse> {
    const updated = await updateDemandStatus(id, newStatus)
    replaceItem(updated)
    return updated
  }

  /** Cancels the demand, which releases its allocations. */
  async function cancel(id: number): Promise<BoughtItemDemandResponse> {
    const updated = await cancelDemand(id)
    replaceItem(updated)
    return updated
  }

  async function setBucket(id: number, bucketId: number | null): Promise<BoughtItemDemandResponse> {
    const updated = await setDemandBucket(id, bucketId)
    replaceItem(updated)
    return updated
  }

  async function remove(id: number): Promise<void> {
    await deleteBoughtItemDemand(id)
    items.value = items.value.filter((item) => item.id !== id)
    total.value = Math.max(0, total.value - 1)
  }

  function replaceItem(updated: BoughtItemDemandResponse): void {
    const index = items.value.findIndex((item) => item.id === updated.id)
    if (index !== -1) {
      items.value[index] = updated
    }
  }

  return {
    loading,
    error,
    items,
    total,
    refreshTrigger,
    refresh,
    triggerRefresh,
    clear,
    create,
    update,
    updateStatus,
    cancel,
    setBucket,
    remove,
    replaceItem,
  }
})
