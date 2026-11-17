import { ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { archiveBoughtItem } from '../api/archiveBoughtItem'
import { createBoughtItem } from '../api/createBoughtItem'
import { getBoughtItems } from '../api/getBoughtItems'
import { mergeBoughtItem } from '../api/mergeBoughtItem'
import { restoreBoughtItem } from '../api/restoreBoughtItem'
import { updateBoughtItem } from '../api/updateBoughtItem'

import type {
  BoughtItemCreateRequest,
  BoughtItemFilterParams,
  BoughtItemUpdateRequest,
} from '../types/boughtItemsRequest'
import type { BoughtItemResponse } from '../types/boughtItemsResponse'

export const useBoughtItemsStore = defineStore('boughtItems', () => {
  const { loading, error, run } = useSequencedFetch(getBoughtItems)

  const items = ref<BoughtItemResponse[]>([])
  const total = ref(0)
  const refreshTrigger = ref(0)

  async function refresh(params?: BoughtItemFilterParams): Promise<void> {
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

  function getById(itemId: number): BoughtItemResponse | undefined {
    return items.value.find((item) => item.id === itemId)
  }

  async function create(payload: BoughtItemCreateRequest): Promise<BoughtItemResponse> {
    return await createBoughtItem(payload)
  }

  async function update(
    itemId: number,
    payload: BoughtItemUpdateRequest,
  ): Promise<BoughtItemResponse> {
    return await updateBoughtItem(itemId, payload)
  }

  async function merge(sourceId: number, targetId: number): Promise<BoughtItemResponse> {
    const result = await mergeBoughtItem(sourceId, targetId)
    items.value = items.value.filter((i) => i.id !== sourceId)
    const targetIndex = items.value.findIndex((i) => i.id === targetId)
    if (targetIndex !== -1) {
      items.value[targetIndex] = result
    }
    return result
  }

  // Archiving changes list membership under the archived filter, so the row
  // is patched and the list refetched.
  async function archive(itemId: number): Promise<BoughtItemResponse> {
    const result = await archiveBoughtItem(itemId)
    const index = items.value.findIndex((i) => i.id === itemId)
    if (index !== -1) items.value[index] = result
    triggerRefresh()
    return result
  }

  async function restore(itemId: number): Promise<BoughtItemResponse> {
    const result = await restoreBoughtItem(itemId)
    const index = items.value.findIndex((i) => i.id === itemId)
    if (index !== -1) items.value[index] = result
    triggerRefresh()
    return result
  }

  function replaceItems(updatedItems: BoughtItemResponse[]): void {
    for (const updatedItem of updatedItems) {
      const index = items.value.findIndex((item) => item.id === updatedItem.id)

      if (index !== -1) {
        items.value[index] = updatedItem
      }
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
    getById,
    create,
    update,
    merge,
    archive,
    restore,
    replaceItems,
  }
})
