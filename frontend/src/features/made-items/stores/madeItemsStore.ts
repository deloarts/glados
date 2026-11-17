import { ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { archiveMadeItem } from '../api/archiveMadeItem'
import { createMadeItem } from '../api/createMadeItem'
import { createMadeItemRevision } from '../api/createMadeItemRevision'
import { getMadeItemRevisions } from '../api/getMadeItemRevisions'
import { getMadeItems } from '../api/getMadeItems'
import { mergeMadeItem } from '../api/mergeMadeItem'
import { restoreMadeItem } from '../api/restoreMadeItem'
import { updateMadeItem } from '../api/updateMadeItem'

import type {
  MadeItemCreateRequest,
  MadeItemCreateRevisionRequest,
  MadeItemFilterParams,
  MadeItemUpdateRequest,
} from '../types/madeItemsRequest'
import type { MadeItemResponse, MadeItemRevisionsResponse } from '../types/madeItemsResponse'

export const useMadeItemsStore = defineStore('madeItems', () => {
  const { loading, error, run } = useSequencedFetch(getMadeItems)

  const items = ref<MadeItemResponse[]>([])
  const total = ref(0)
  const refreshTrigger = ref(0)

  async function refresh(params?: MadeItemFilterParams): Promise<void> {
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

  function getById(itemId: number): MadeItemResponse | undefined {
    return items.value.find((item) => item.id === itemId)
  }

  async function create(payload: MadeItemCreateRequest): Promise<MadeItemResponse> {
    return await createMadeItem(payload)
  }

  async function update(itemId: number, payload: MadeItemUpdateRequest): Promise<MadeItemResponse> {
    return await updateMadeItem(itemId, payload)
  }

  /** Uncached, since only a per-open Select needs it. */
  async function getRevisions(itemId: number): Promise<MadeItemRevisionsResponse> {
    return await getMadeItemRevisions(itemId)
  }

  async function createRevision(
    predecessorId: number,
    payload: MadeItemCreateRevisionRequest,
  ): Promise<MadeItemResponse> {
    const created = await createMadeItemRevision(predecessorId, payload)

    // The predecessor's status and successor link change in the same call, so
    // the cached row is patched.
    const index = items.value.findIndex((item) => item.id === predecessorId)
    if (index !== -1) {
      const predecessor = items.value[index]!
      items.value[index] = {
        ...predecessor,
        status: payload.predecessor_status,
        successor_item_id:
          payload.predecessor_status === 'replaced' ? created.id : predecessor.successor_item_id,
      }
    }

    return created
  }

  async function merge(sourceId: number, targetId: number): Promise<MadeItemResponse> {
    const result = await mergeMadeItem(sourceId, targetId)
    items.value = items.value.filter((i) => i.id !== sourceId)
    const targetIndex = items.value.findIndex((i) => i.id === targetId)
    if (targetIndex !== -1) {
      items.value[targetIndex] = result
    }
    return result
  }

  // Archiving changes list membership under the archived filter, so the row
  // is patched and the list refetched.
  async function archive(itemId: number): Promise<MadeItemResponse> {
    const result = await archiveMadeItem(itemId)
    const index = items.value.findIndex((i) => i.id === itemId)
    if (index !== -1) items.value[index] = result
    triggerRefresh()
    return result
  }

  async function restore(itemId: number): Promise<MadeItemResponse> {
    const result = await restoreMadeItem(itemId)
    const index = items.value.findIndex((i) => i.id === itemId)
    if (index !== -1) items.value[index] = result
    triggerRefresh()
    return result
  }

  function replaceItems(updatedItems: MadeItemResponse[]): void {
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
    getRevisions,
    createRevision,
    merge,
    archive,
    restore,
    replaceItems,
  }
})
