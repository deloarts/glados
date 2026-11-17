import { ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import {
  createMadeItemDemand,
  getMadeItemDemands,
  updateMadeItemDemand,
  updateMadeItemDemandStatus,
  cancelMadeItemDemand,
  setMadeItemDemandBucket,
} from '../api/madeItemDemandsApi'
import { deleteMadeItemDemand } from '../api/deleteMadeItemDemand'
import { getMadeItemDemandCancelImpact } from '../api/getMadeItemDemandCancelImpact'

import type {
  MadeItemDemandCreateRequest,
  MadeItemDemandFilterParams,
  MadeItemDemandUpdateRequest,
} from '../types/madeItemsDemandsRequest'
import type {
  MadeItemDemandCancelImpact,
  MadeItemDemandResponse,
  MadeItemDemandStatus,
} from '../types/madeItemsDemandsResponse'

export const useMadeItemsDemandsStore = defineStore('madeItemsDemands', () => {
  const { loading, error, run } = useSequencedFetch(getMadeItemDemands)
  const items = ref<MadeItemDemandResponse[]>([])
  const total = ref(0)
  const refreshTrigger = ref(0)

  async function refresh(params?: MadeItemDemandFilterParams): Promise<void> {
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

  async function create(payload: MadeItemDemandCreateRequest): Promise<MadeItemDemandResponse> {
    return await createMadeItemDemand(payload)
  }

  async function update(
    id: number,
    payload: MadeItemDemandUpdateRequest,
  ): Promise<MadeItemDemandResponse> {
    const updated = await updateMadeItemDemand(id, payload)
    replaceItem(updated)
    return updated
  }

  async function updateStatus(
    id: number,
    newStatus: MadeItemDemandStatus,
  ): Promise<MadeItemDemandResponse> {
    const updated = await updateMadeItemDemandStatus(id, newStatus)
    replaceItem(updated)
    return updated
  }

  /**
   * Cancels the demand with everything that exists only because of it,
   * as fetchCancelImpact lists it.
   */
  async function cancel(id: number): Promise<MadeItemDemandResponse> {
    const updated = await cancelMadeItemDemand(id)
    replaceItem(updated)
    return updated
  }

  async function setBucket(id: number, bucketId: number | null): Promise<MadeItemDemandResponse> {
    const updated = await setMadeItemDemandBucket(id, bucketId)
    replaceItem(updated)
    return updated
  }

  /** What canceling this demand would take down, for the confirmation dialog. */
  async function fetchCancelImpact(id: number): Promise<MadeItemDemandCancelImpact> {
    return await getMadeItemDemandCancelImpact(id)
  }

  async function remove(id: number): Promise<void> {
    await deleteMadeItemDemand(id)
    items.value = items.value.filter((item) => item.id !== id)
    total.value = Math.max(0, total.value - 1)
  }

  function replaceItem(updated: MadeItemDemandResponse): void {
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
    fetchCancelImpact,
    remove,
    replaceItem,
  }
})
