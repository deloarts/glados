import { ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import {
  createSourceItemDemand,
  getSourceItemDemands,
  updateSourceItemDemand,
  updateSourceItemDemandStatus,
  setSourceItemDemandBucket,
} from '../api/sourceItemDemandsApi'
import {
  cancelSourceItemDemand,
  cancelSourceItemDemandByStatus,
} from '../api/cancelSourceItemDemand'

import type {
  SourceItemDemandCreateRequest,
  SourceItemDemandFilterParams,
  SourceItemDemandUpdateRequest,
} from '../types/sourceItemDemandsRequest'
import type {
  SourceItemDemandResponse,
  SourceItemDemandStatus,
} from '../types/sourceItemDemandsResponse'

export const useSourceItemDemandsStore = defineStore('sourceItemDemands', () => {
  const { loading, error, run } = useSequencedFetch(getSourceItemDemands)
  const items = ref<SourceItemDemandResponse[]>([])
  const total = ref(0)
  const refreshTrigger = ref(0)

  async function refresh(params?: SourceItemDemandFilterParams): Promise<void> {
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

  async function create(payload: SourceItemDemandCreateRequest): Promise<SourceItemDemandResponse> {
    return await createSourceItemDemand(payload)
  }

  async function update(
    id: number,
    payload: SourceItemDemandUpdateRequest,
  ): Promise<SourceItemDemandResponse> {
    const updated = await updateSourceItemDemand(id, payload)
    replaceItem(updated)
    return updated
  }

  async function updateStatus(
    id: number,
    newStatus: SourceItemDemandStatus,
  ): Promise<SourceItemDemandResponse> {
    const updated = await updateSourceItemDemandStatus(id, newStatus)
    replaceItem(updated)
    return updated
  }

  async function cancel(id: number, cancelLot: boolean): Promise<SourceItemDemandResponse> {
    const updated = await cancelSourceItemDemand(id, cancelLot)
    replaceItem(updated)
    return updated
  }

  async function cancelByStatus(id: number, cancelLot: boolean): Promise<SourceItemDemandResponse> {
    const updated = await cancelSourceItemDemandByStatus(id, cancelLot)
    replaceItem(updated)
    return updated
  }

  async function setBucket(
    id: number,
    bucketId: number | null,
  ): Promise<SourceItemDemandResponse> {
    const updated = await setSourceItemDemandBucket(id, bucketId)
    replaceItem(updated)
    return updated
  }

  function replaceItem(updated: SourceItemDemandResponse): void {
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
    cancelByStatus,
    setBucket,
    replaceItem,
  }
})
