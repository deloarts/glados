import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { SseHttpError } from '@/core/realtime/sseClient'

import { AutoPlanConnectionLostError, streamAutoPlanSchedule } from '../api/autoPlanScheduleStream'
import { getAutoPlanRunStatus } from '../api/getAutoPlanRunStatus'

import type {
  AutoPlanProgressEvent,
  AutoPlanProgressOrder,
  AutoPlanProgressStage,
  AutoPlanRequest,
  AutoPlanResponse,
  AutoPlanRun,
} from '../types/scheduleBoardResponse'

const OBSERVER_POLL_MS = 3000
// Runs only while a run is believed active, so a missed end signal can
// never leave a button spinning.
const SAFETY_POLL_MS = 30000

// Caps the feed, which lives until the next run.
const FEED_CAP = 1000

/** Thrown by run() when a run is already in flight; the dialog attaches to it. */
export class AutoPlanAlreadyRunningError extends Error {
  constructor() {
    super('An auto-plan run is already in progress')
    this.name = 'AutoPlanAlreadyRunningError'
  }
}

/**
 * Thrown when another run holds the mutex (409); the dialog switches to the
 * observer view.
 */
export class AutoPlanRunTakenError extends Error {
  constructor() {
    super('Another auto-plan run is already in progress')
    this.name = 'AutoPlanRunTakenError'
  }
}

// App-scoped so a run outlives the dialog and route changes.
export const useAutoPlanRunStore = defineStore('autoPlanRun', () => {
  const status = ref<'idle' | 'running'>('idle')
  const stage = ref<AutoPlanProgressStage | null>(null)
  const current = ref<number | null>(null)
  const total = ref<number | null>(null)
  const feed = ref<AutoPlanProgressOrder[]>([])

  // Exactly one of these is set once a run ends.
  const result = ref<AutoPlanResponse | null>(null)
  const errorDetail = ref<string | null>(null)
  const connectionLost = ref(false)

  // The app-wide run, from fetchStatus(); `status` covers only this tab's.
  const activeRun = ref<AutoPlanRun | null>(null)

  // Sequenced, because two polls and direct calls overlap.
  const { run: runStatusFetch } = useSequencedFetch(getAutoPlanRunStatus)

  let observerPollHandle: ReturnType<typeof setInterval> | null = null
  let safetyPollHandle: ReturnType<typeof setInterval> | null = null

  // null means indeterminate.
  const percent = computed<number | null>(() => {
    if (stage.value !== 'placing' && stage.value !== 'recomputing') return null
    if (current.value === null || total.value === null || total.value === 0) return null
    return Math.min(100, Math.max(0, (current.value / total.value) * 100))
  })

  const isMine = computed<boolean>(() => {
    const run = activeRun.value
    if (run === null) return false
    const currentUserId = useCurrentUserStore().user?.id
    return currentUserId !== undefined && run.user_id === currentUserId
  })

  // Trigger buttons spin for any active run, own or not.
  const anyRunActive = computed<boolean>(() => activeRun.value !== null)

  function resetState(): void {
    stage.value = null
    current.value = null
    total.value = null
    feed.value = []
    result.value = null
    errorDetail.value = null
    connectionLost.value = false
  }

  function onProgress(event: AutoPlanProgressEvent): void {
    stage.value = event.stage
    current.value = event.current
    total.value = event.total
    const order = event.order
    if (event.stage === 'placing' && order) {
      // A second frame for a listed order reports a placement the write
      // dropped, so it replaces the row and the feed ends as the result.
      const listed = feed.value.findIndex((entry) => entry.order_id === order.order_id)
      if (listed !== -1) {
        feed.value.splice(listed, 1, order)
        return
      }
      feed.value.push(order)
      if (feed.value.length > FEED_CAP) {
        feed.value.splice(0, feed.value.length - FEED_CAP)
      }
    }
  }

  // A failure keeps the previous value; the next poll retries.
  async function fetchStatus(): Promise<void> {
    const response = await runStatusFetch()
    if (!response) return

    activeRun.value = response.run

    // The safety poll starts and stops itself with the run status.
    if (activeRun.value !== null) {
      startSafetyPolling()
    } else {
      stopSafetyPolling()
    }
  }

  function startSafetyPolling(): void {
    if (safetyPollHandle !== null) return
    safetyPollHandle = setInterval(() => {
      void fetchStatus()
    }, SAFETY_POLL_MS)
  }

  function stopSafetyPolling(): void {
    if (safetyPollHandle === null) return
    clearInterval(safetyPollHandle)
    safetyPollHandle = null
  }

  function startObserverPolling(): void {
    if (observerPollHandle !== null) return
    observerPollHandle = setInterval(() => {
      void fetchStatus()
    }, OBSERVER_POLL_MS)
  }

  function stopObserverPolling(): void {
    if (observerPollHandle === null) return
    clearInterval(observerPollHandle)
    observerPollHandle = null
  }

  async function run(payload: AutoPlanRequest): Promise<AutoPlanResponse> {
    if (status.value === 'running') {
      throw new AutoPlanAlreadyRunningError()
    }

    resetState()
    status.value = 'running'

    // Never aborted: closing the dialog must not stop the run.
    const controller = new AbortController()

    try {
      const response = await streamAutoPlanSchedule(payload, onProgress, controller.signal)
      result.value = response
      return response
    } catch (error) {
      if (error instanceof AutoPlanConnectionLostError) {
        connectionLost.value = true
        throw error
      }
      if (error instanceof SseHttpError && error.status === 409) {
        await fetchStatus()
        throw new AutoPlanRunTakenError()
      }
      errorDetail.value = error instanceof Error ? error.message : String(error)
      throw error
    } finally {
      status.value = 'idle'
    }
  }

  return {
    status,
    stage,
    current,
    total,
    percent,
    feed,
    result,
    errorDetail,
    connectionLost,
    activeRun,
    isMine,
    anyRunActive,
    fetchStatus,
    startObserverPolling,
    stopObserverPolling,
    run,
  }
})
