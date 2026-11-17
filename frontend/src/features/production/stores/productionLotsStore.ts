import { ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { createLot } from '../api/createLot'
import { getLots } from '../api/getLots'
import { updateLot } from '../api/updateLot'
import { cancelLot } from '../api/cancelLot'
import { completeLot } from '../api/completeLot'

import type {
  LotCreateRequest,
  LotFilterParams,
  LotUpdateRequest,
} from '../types/productionLotsRequest'
import type { LotResponse, LotSummaryResponse } from '../types/productionLotsResponse'

export const useProductionLotsStore = defineStore('productionLots', () => {
  const { loading, error, run } = useSequencedFetch(getLots)
  const items = ref<LotSummaryResponse[]>([])
  const total = ref(0)
  const refreshTrigger = ref(0)

  async function refresh(params?: LotFilterParams): Promise<void> {
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

  async function create(payload: LotCreateRequest): Promise<LotResponse> {
    const created = await createLot(payload)
    triggerRefresh()
    return created
  }

  // An edit or an irreversible action carries the lot's edit version as the
  // caller showed it, so a concurrent change answers 409.
  async function update(id: number, payload: LotUpdateRequest): Promise<LotResponse> {
    const updated = await updateLot(id, payload)
    triggerRefresh()
    return updated
  }

  async function cancel(
    id: number,
    editVersion: number,
    reason?: string | null,
  ): Promise<LotResponse> {
    const updated = await cancelLot(id, { reason, expected_edit_version: editVersion })
    triggerRefresh()
    return updated
  }

  async function complete(
    id: number,
    editVersion: number,
    reason?: string | null,
  ): Promise<LotResponse> {
    const updated = await completeLot(id, { reason, expected_edit_version: editVersion })
    triggerRefresh()
    return updated
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
    cancel,
    complete,
  }
})
