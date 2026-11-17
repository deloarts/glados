import { onScopeDispose, watch } from 'vue'

import { useLiveStore } from './liveStore'
import type { LiveSignal } from './types'

export interface UseLiveRefreshOptions {
  /** Quiet period after the last signal before the refetch runs. */
  debounceMs?: number
  /** Only a signal this accepts schedules a refetch, for views showing part of a resource. */
  filter?: (signal: LiveSignal) => boolean
}

/**
 * For derived/aggregated views with no stable per-row list endpoint (WIP,
 * capacity, queue, planning Gantt, timelines, lot detail); there's no row
 * to patch, so any signal on a watched resource just debounces one full
 * `refetch()`. Coarser than useLiveRows on purpose.
 *
 * After the live stream reconnects, the view refetches once right away to
 * pick up whatever changed while it was disconnected. A refetch that fails
 * is dropped quietly, since the next signal or reconnect retries it.
 */
export function useLiveRefresh(
  resources: string[],
  refetch: () => unknown,
  options: UseLiveRefreshOptions = {},
): void {
  const { debounceMs = 500, filter } = options
  const live = useLiveStore()

  let timer: ReturnType<typeof setTimeout> | null = null

  function cancelScheduled(): void {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  function runRefetch(): void {
    try {
      Promise.resolve(refetch()).catch(() => {})
    } catch {
      // A synchronous throw is dropped like a rejection.
    }
  }

  function scheduleRefetch(signal: LiveSignal): void {
    if (filter && !filter(signal)) return
    cancelScheduled()
    timer = setTimeout(() => {
      timer = null
      runRefetch()
    }, debounceMs)
  }

  const unsubscribes = resources.map((resource) => live.on(resource, scheduleRefetch))

  watch(
    () => live.reconnectCount,
    () => {
      cancelScheduled()
      runRefetch()
    },
  )

  onScopeDispose(() => {
    unsubscribes.forEach((unsubscribe) => unsubscribe())
    cancelScheduled()
  })
}
