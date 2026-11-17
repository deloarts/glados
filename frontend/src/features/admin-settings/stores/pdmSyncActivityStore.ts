import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { getPdmSyncActivity } from '../api/getPdmSyncActivity'

import type { PdmSyncActivity } from '../types/adminSettingsTypes'

/** While nothing runs, a light check for a sync started elsewhere. */
const IDLE_POLL_MS = 10000
/** While a sync is requested or running, or the dialog is open. */
const ACTIVE_POLL_MS = 2000

/**
 * Backs the "Synchronize with PDM" button and its activity dialog. `busy`
 * is true from the moment a synchronisation is requested until its poll run
 * finishes. Polling uses a chained `setTimeout`, so a slow request never
 * overlaps the next one, and runs faster while the sync is busy or the
 * dialog is open. Consumers call `startPolling()` on mount and
 * `stopPolling()` on unmount; the store keeps polling while any consumer
 * remains.
 */
export const usePdmSyncActivityStore = defineStore('pdmSyncActivity', () => {
  const { loading, error, run: runFetch } = useSequencedFetch(getPdmSyncActivity)
  const activity = ref<PdmSyncActivity | null>(null)
  const dialogOpen = ref(false)

  const busy = computed(() => !!activity.value && (activity.value.requested || !!activity.value.run))

  let consumers = 0
  let timer: ReturnType<typeof setTimeout> | null = null

  function clearTimer(): void {
    if (timer === null) return
    clearTimeout(timer)
    timer = null
  }

  function schedule(): void {
    clearTimer()
    if (consumers === 0) return
    const delay = busy.value || dialogOpen.value ? ACTIVE_POLL_MS : IDLE_POLL_MS
    timer = setTimeout(() => {
      void refresh()
    }, delay)
  }

  async function refresh(): Promise<void> {
    const response = await runFetch()
    if (response) activity.value = response
    schedule()
  }

  function startPolling(): void {
    consumers += 1
    if (consumers === 1) void refresh()
  }

  function stopPolling(): void {
    consumers = Math.max(0, consumers - 1)
    if (consumers === 0) clearTimer()
  }

  /**
   * Marks the sync as requested right away, before the next poll confirms
   * it, so the button shows its spinner without a delay.
   */
  function markRequested(): void {
    if (activity.value) activity.value = { ...activity.value, requested: true }
    void refresh()
  }

  function setDialogOpen(open: boolean): void {
    dialogOpen.value = open
    if (open) void refresh()
  }

  return {
    loading,
    error,
    activity,
    dialogOpen,

    busy,

    refresh,
    startPolling,
    stopPolling,
    markRequested,
    setDialogOpen,
  }
})
