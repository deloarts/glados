import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { dismissPdmFile } from '../api/dismissPdmFile'
import { getPdmFiles } from '../api/getPdmFiles'
import { retryPdmFile } from '../api/retryPdmFile'

import type {
  PdmFileKind,
  PdmFileSnapshot,
  PdmFileSnapshotFilterParams,
  PdmFileSyncState,
} from '../types/adminSettingsTypes'

/**
 * Paged store backing the admin "PDM files" tab, same shape as usersStore's
 * management table but with no separate picker-facing list, since this
 * resource has no picker use anywhere else. `search`/`syncState`/`kind`
 * are the ControlsBar/ViewsBar filters `refresh` folds into the request.
 * `retry` optimistically flips the row back to `pending` (mirroring what the
 * backend's retry endpoint itself does before the worker picks it up);
 * `dismiss` replaces the row with the server's response since dismissing
 * also clears `last_error`/`has_parked_payload`, which a local patch could
 * get wrong.
 */
export const usePdmFilesStore = defineStore('pdmFiles', () => {
  const { loading, error, run } = useSequencedFetch(getPdmFiles)
  const items = ref<PdmFileSnapshot[]>([])
  const total = ref(0)
  const search = ref('')
  const syncState = ref<PdmFileSyncState | null>(null)
  const kind = ref<PdmFileKind | null>(null)

  const hasActiveFilters = computed<boolean>(
    () => search.value !== '' || syncState.value !== null || kind.value !== null,
  )

  function buildParams(page?: { skip: number; limit: number }): PdmFileSnapshotFilterParams {
    const params: PdmFileSnapshotFilterParams = {}

    if (search.value) params.search = search.value
    if (syncState.value) params.sync_state = syncState.value
    if (kind.value) params.kind = kind.value

    if (page) {
      params.skip = page.skip
      params.limit = page.limit
    }

    return params
  }

  async function refresh(page?: { skip: number; limit: number }): Promise<void> {
    const response = await run(buildParams(page))
    if (!response) return

    items.value = response.items
    total.value = response.total
  }

  function clearAll(): void {
    search.value = ''
    syncState.value = null
    kind.value = null
  }

  async function retry(id: number): Promise<void> {
    await retryPdmFile(id)
    const row = items.value.find((f) => f.id === id)
    if (row) row.sync_state = 'pending'
  }

  async function dismiss(id: number): Promise<void> {
    const updated = await dismissPdmFile(id)
    const index = items.value.findIndex((f) => f.id === id)
    if (index !== -1) items.value[index] = updated
  }

  return {
    loading,
    error,
    items,
    total,
    search,
    syncState,
    kind,

    hasActiveFilters,

    refresh,
    clearAll,
    retry,
    dismiss,
  }
})
