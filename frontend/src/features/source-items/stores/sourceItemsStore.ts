import { ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { sourceItemsApi } from '../api/sourceItemsApi'

import type {
  SourceItemCreateRequest,
  SourceItemFilterParams,
  SourceItemUpdateRequest,
} from '../types/sourceItemsRequest'
import type { SourceItemResponse } from '../types/sourceItemsResponse'

export const useSourceItemsStore = defineStore('sourceItems', () => {
  const { loading, error, run } = useSequencedFetch(sourceItemsApi.list)

  const items = ref<SourceItemResponse[]>([])
  const total = ref(0)
  const refreshTrigger = ref(0)

  async function refresh(params?: SourceItemFilterParams): Promise<void> {
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

  function getById(itemId: number): SourceItemResponse | undefined {
    return items.value.find((item) => item.id === itemId)
  }

  async function create(payload: SourceItemCreateRequest): Promise<SourceItemResponse> {
    return await sourceItemsApi.create(payload)
  }

  async function update(
    itemId: number,
    payload: SourceItemUpdateRequest,
  ): Promise<SourceItemResponse> {
    return await sourceItemsApi.update(itemId, payload)
  }

  // Archiving changes list membership under the archived filter, so the row
  // is patched and the list refetched.
  async function archive(itemId: number): Promise<SourceItemResponse> {
    const result = await sourceItemsApi.archive(itemId)
    const index = items.value.findIndex((item) => item.id === itemId)
    if (index !== -1) items.value[index] = result
    triggerRefresh()
    return result
  }

  async function restore(itemId: number): Promise<SourceItemResponse> {
    const result = await sourceItemsApi.restore(itemId)
    const index = items.value.findIndex((item) => item.id === itemId)
    if (index !== -1) items.value[index] = result
    triggerRefresh()
    return result
  }

  function replaceItems(updatedItems: SourceItemResponse[]): void {
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
    archive,
    restore,
    replaceItems,
  }
})
