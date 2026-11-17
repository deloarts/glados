import { ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { getPdmReconciliation } from '../api/getPdmReconciliation'
import { getPdmReconciliationFindings } from '../api/getPdmReconciliationFindings'
import { requestPdmReconciliation } from '../api/requestPdmReconciliation'
import { retryPdmVaultFile } from '../api/retryPdmVaultFile'

import type {
  PdmFileKind,
  PdmReconciliationCategory,
  PdmReconciliationFinding,
  PdmSyncRun,
} from '../types/adminSettingsTypes'

const SUMMARY_POLL_MS = 5000

/**
 * Backs the admin "View reconciliation" dialog: the latest run
 * summary plus per-category counts (`loadSummary`), and a second, paged,
 * `category`/`kind`/`search`/`partNumber`/`message`-filtered findings list
 * for that run (`loadFindings`). `requestRun` queues a new run and immediately reloads
 * the summary, which is what turns the just-queued run's `finished_at:
 * null` into the trigger for self-scheduling polling: `loadSummary`
 * reschedules itself every `SUMMARY_POLL_MS` while the run it fetched is
 * still open, and stops as soon as one comes back finished (or the report
 * has never run at all). Using a chained `setTimeout` rather than
 * `setInterval` means a slow request can never overlap with the next
 * tick's own request.
 *
 * The dialog must call `stopPolling()` on unmount: closing it does not by
 * itself imply the run finished, and an orphaned timer would keep firing
 * fetches for a store that no longer has a visible consumer.
 */
export const usePdmReconciliationStore = defineStore('pdmReconciliation', () => {
  const { loading, error, run: runSummaryFetch } = useSequencedFetch(getPdmReconciliation)
  const run = ref<PdmSyncRun | null>(null)
  const counts = ref<Record<string, number>>({})

  const {
    loading: findingsLoading,
    error: findingsError,
    run: runFindingsFetch,
  } = useSequencedFetch(getPdmReconciliationFindings)
  const findings = ref<PdmReconciliationFinding[]>([])
  const findingsTotal = ref(0)

  const category = ref<PdmReconciliationCategory | null>(null)
  const kind = ref<PdmFileKind | null>(null)
  const search = ref('')
  const partNumber = ref('')
  const message = ref('')

  const requesting = ref(false)

  let pollTimer: ReturnType<typeof setTimeout> | null = null

  function stopPolling(): void {
    if (pollTimer === null) return
    clearTimeout(pollTimer)
    pollTimer = null
  }

  async function loadSummary(): Promise<void> {
    const response = await runSummaryFetch()
    if (!response) return

    run.value = response.run
    counts.value = response.counts

    stopPolling()
    if (response.run && response.run.finished_at === null) {
      pollTimer = setTimeout(() => {
        void loadSummary()
      }, SUMMARY_POLL_MS)
    }
  }

  function buildFindingsParams(page?: { skip: number; limit: number }) {
    const params: {
      skip?: number
      limit?: number
      category?: PdmReconciliationCategory
      kind?: PdmFileKind
      search?: string
      part_number?: string
      message?: string
    } = {}

    if (category.value) params.category = category.value
    if (kind.value) params.kind = kind.value
    if (search.value) params.search = search.value
    const partNumberText = partNumber.value.trim()
    if (partNumberText) params.part_number = partNumberText
    const messageText = message.value.trim()
    if (messageText) params.message = messageText

    if (page) {
      params.skip = page.skip
      params.limit = page.limit
    }

    return params
  }

  async function loadFindings(page?: { skip: number; limit: number }): Promise<void> {
    const response = await runFindingsFetch(buildFindingsParams(page))
    if (!response) return

    findings.value = response.items
    findingsTotal.value = response.total
  }

  /**
   * Queues a new run (`deep` selects the deep reconciliation option) and
   * reloads the summary so the dialog sees the freshly queued,
   * not-yet-finished run (and its polling) right away rather than waiting
   * for the next manual refresh.
   */
  async function requestRun(deep: boolean): Promise<void> {
    requesting.value = true
    try {
      await requestPdmReconciliation(deep)
      await loadSummary()
    } finally {
      requesting.value = false
    }
  }

  /** Asks the trigger worker to re-read one finding's file now. */
  async function recheckFile(fileId: number): Promise<void> {
    await retryPdmVaultFile(fileId)
  }

  return {
    loading,
    error,
    run,
    counts,
    findingsLoading,
    findingsError,
    findings,
    findingsTotal,
    category,
    kind,
    search,
    partNumber,
    message,
    requesting,

    recheckFile,
    loadSummary,
    loadFindings,
    buildFindingsParams,
    requestRun,
    stopPolling,
  }
})
