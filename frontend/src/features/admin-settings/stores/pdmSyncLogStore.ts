import { ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { dateToParam } from '@/core/utils/dates'
import { getPdmSyncRunEntries } from '../api/getPdmSyncRunEntries'
import { getPdmSyncRuns } from '../api/getPdmSyncRuns'

import type {
  PdmFileKind,
  PdmSyncEntryAction,
  PdmSyncRun,
  PdmSyncRunEntry,
  PdmSyncRunEntryFilterParams,
  PdmSyncRunFilterParams,
  PdmSyncTrigger,
} from '../types/adminSettingsTypes'

/**
 * Backs the admin sync log dialog: a paged, newest-first runs list
 * (`refresh`, same shape as pdmFilesStore's) plus a second, per-run paged
 * entries list. `selectedRunId` and `action` are plain state, set directly
 * by the dialog the way pdmFilesStore's `search`/`syncState`/`kind` are;
 * `loadEntries` folds the current `action` filter into the request but
 * does not touch `selectedRunId` itself, so the dialog decides when a
 * selection changes (row click) versus when the same selection is merely
 * repaged or refiltered.
 *
 * The runs list has its own row filters (`triggers`, the `startedFrom`/
 * `startedTo` day range and `runError` text), the entries list adds `kind`
 * and a file name or path `search` next to `action`. All of them are plain
 * state the dialog binds to and are folded into the next request; an empty
 * filter is left out of the params entirely.
 */
export const usePdmSyncLogStore = defineStore('pdmSyncLog', () => {
  const { loading, error, run } = useSequencedFetch(getPdmSyncRuns)
  const runs = ref<PdmSyncRun[]>([])
  const total = ref(0)

  const selectedRunId = ref<number | null>(null)

  const triggers = ref<PdmSyncTrigger[]>([])
  const startedFrom = ref<Date | null>(null)
  const startedTo = ref<Date | null>(null)
  const runError = ref('')

  const {
    loading: entriesLoading,
    error: entriesError,
    run: runEntries,
  } = useSequencedFetch(getPdmSyncRunEntries)
  const entries = ref<PdmSyncRunEntry[]>([])
  const entriesTotal = ref(0)
  const action = ref<PdmSyncEntryAction | null>(null)
  const kind = ref<PdmFileKind | null>(null)
  const search = ref('')

  function buildRunParams(page?: { skip: number; limit: number }): PdmSyncRunFilterParams {
    const params: PdmSyncRunFilterParams = page ? { skip: page.skip, limit: page.limit } : {}
    if (triggers.value.length) params.trigger = [...triggers.value]
    const from = dateToParam(startedFrom.value)
    if (from) params.started_from = from
    const to = dateToParam(startedTo.value)
    if (to) params.started_to = to
    const errorText = runError.value.trim()
    if (errorText) params.error = errorText
    return params
  }

  async function refresh(page?: { skip: number; limit: number }): Promise<void> {
    const params = buildRunParams(page)
    // No page and no filter keeps the bare call the runs list always made.
    const response = await run(Object.keys(params).length ? params : undefined)
    if (!response) return

    runs.value = response.items
    total.value = response.total
  }

  async function loadEntries(runId: number, page?: { skip: number; limit: number }): Promise<void> {
    const searchText = search.value.trim()
    const params: PdmSyncRunEntryFilterParams = {
      ...(action.value ? { action: action.value } : {}),
      ...(kind.value ? { kind: kind.value } : {}),
      ...(searchText ? { search: searchText } : {}),
      ...(page ? { skip: page.skip, limit: page.limit } : {}),
    }
    const response = await runEntries(runId, params)
    if (!response) return

    entries.value = response.items
    entriesTotal.value = response.total
  }

  function clearSelection(): void {
    selectedRunId.value = null
    entries.value = []
    entriesTotal.value = 0
  }

  return {
    loading,
    error,
    runs,
    total,
    selectedRunId,
    triggers,
    startedFrom,
    startedTo,
    runError,
    entriesLoading,
    entriesError,
    entries,
    entriesTotal,
    action,
    kind,
    search,

    refresh,
    loadEntries,
    clearSelection,
  }
})
