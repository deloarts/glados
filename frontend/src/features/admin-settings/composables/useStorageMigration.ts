import { computed, onBeforeUnmount, ref } from 'vue'

import { SseHttpError } from '@/core/realtime/sseClient'

import { getStorageMigrationStatus } from '../api/getStorageMigrationStatus'
import {
  StorageMigrationConnectionLostError,
  streamStorageMigration,
} from '../api/streamStorageMigration'
import { useAdminSettingsStore } from '../stores/adminSettingsStore'

import type {
  StorageMigrationResult,
  StorageMigrationStatus,
  UpdateStorageSettingsCommand,
} from '../types/adminSettingsTypes'

// Matches the backend heartbeat closely enough: the status snapshot only
// changes every 10s, the end of a run shows up within this interval.
const OBSERVE_INTERVAL_MS = 3000

/**
 * The storage migration as the Storage tab sees it. `running` follows this
 * tab's own stream, `observing` polls the status endpoint for a migration
 * the tab did not start or whose stream dropped (a reload, a lost
 * connection, another admin's run). Either way the copy itself runs on the
 * server and is never stopped from here.
 */
export function useStorageMigration() {
  const store = useAdminSettingsStore()

  const phase = ref<'idle' | 'running' | 'observing' | 'done' | 'finishedElsewhere'>('idle')
  const current = ref<number | null>(null)
  const total = ref<number | null>(null)
  const currentKey = ref<string | null>(null)
  const startedBy = ref<string | null>(null)
  const result = ref<StorageMigrationResult | null>(null)

  const percent = computed(() =>
    current.value !== null && total.value ? Math.round((current.value / total.value) * 100) : null,
  )

  let controller: AbortController | null = null
  let pollHandle: ReturnType<typeof setInterval> | null = null

  function reset() {
    current.value = null
    total.value = null
    currentKey.value = null
    startedBy.value = null
    result.value = null
  }

  function stopObserving() {
    if (pollHandle !== null) {
      clearInterval(pollHandle)
      pollHandle = null
    }
  }

  function applyStatus(status: StorageMigrationStatus) {
    if (!status.run) return
    current.value = status.run.current
    total.value = status.run.total
    currentKey.value = status.run.detail
    startedBy.value = status.run.user_name
  }

  async function pollOnce() {
    let status: StorageMigrationStatus
    try {
      status = await getStorageMigrationStatus()
    } catch {
      // A failed poll is retried on the next tick.
      return
    }
    if (status.running) {
      applyStatus(status)
      return
    }
    stopObserving()
    await store.fetch()
    phase.value = 'finishedElsewhere'
  }

  function observe() {
    phase.value = 'observing'
    stopObserving()
    pollHandle = setInterval(() => void pollOnce(), OBSERVE_INTERVAL_MS)
  }

  /**
   * Switches to `observing` when a migration is already running; returns
   * whether one is.
   */
  async function checkRunning(): Promise<boolean> {
    let status: StorageMigrationStatus
    try {
      status = await getStorageMigrationStatus()
    } catch {
      return false
    }
    if (!status.running) return false
    reset()
    applyStatus(status)
    observe()
    return true
  }

  /**
   * Starts a migration and follows its stream. Rejects with the server's
   * message when the migration cannot start or fails as a whole.
   */
  async function start(cmd: UpdateStorageSettingsCommand): Promise<void> {
    reset()
    phase.value = 'running'
    controller = new AbortController()
    try {
      result.value = await streamStorageMigration(
        cmd,
        (ev) => {
          current.value = ev.current
          total.value = ev.total
          currentKey.value = ev.key
        },
        controller.signal,
      )
      if (result.value.committed) await store.fetch()
      phase.value = 'done'
    } catch (error) {
      if (controller.signal.aborted) return
      // The copy keeps going on the server, or another one already does.
      if (
        error instanceof StorageMigrationConnectionLostError ||
        (error instanceof SseHttpError && error.status === 409)
      ) {
        observe()
        return
      }
      phase.value = 'idle'
      throw error
    } finally {
      controller = null
    }
  }

  onBeforeUnmount(() => {
    controller?.abort()
    stopObserving()
  })

  return {
    phase,
    current,
    total,
    currentKey,
    startedBy,
    result,
    percent,
    checkRunning,
    start,
    reset: () => {
      if (phase.value === 'running' || phase.value === 'observing') return
      reset()
      phase.value = 'idle'
    },
  }
}
