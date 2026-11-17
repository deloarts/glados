import { onScopeDispose, watch } from 'vue'
import type { Ref } from 'vue'

import { useLiveStore } from './liveStore'
import { LIVE_COALESCE_MS } from './constants'
import type { LiveSignal } from './types'

interface RowLike {
  id: number
}

export interface UseLiveRowsOptions<T extends RowLike> {
  /** LiveResource value this table subscribes to. */
  resource: string
  items: Ref<T[]>
  total: Ref<number>
  /**
   * Refetch exactly these rows through the resource's list endpoint,
   * using the table's *current filters* but no skip/limit/order_by. The
   * caller owns buildFilterParams(). The response's own `total` is the
   * count of matching ids, not the table total, and must be ignored.
   */
  fetchByIds: (ids: number[]) => Promise<T[]>
  /**
   * Full foreground refetch (the table's existing fetchItems), used for
   * creates, bulk collapses, and missed-update recovery after a
   * reconnect. These are expected to show the normal loading state.
   */
  onFullRefresh: () => void
}

/**
 * Wires one table's `items`/`total` to live row-sync signals for
 * `resource`. Call from the component that owns buildParams()/fetchItems()
 * (the table itself, or its wrapping view for resources like production
 * lots) so the subscription's lifetime is exactly the table's mount
 * lifetime.
 *
 * Deliberately does not suppress signals whose actor_id is the current
 * user: a user with two tabs open on the same table would otherwise watch
 * one of them go stale after editing from the other.
 */
export function useLiveRows<T extends RowLike>(options: UseLiveRowsOptions<T>): void {
  const live = useLiveStore()

  const pending = new Set<number>()
  let flushTimer: ReturnType<typeof setTimeout> | null = null

  function scheduleFlush(): void {
    if (flushTimer) return
    flushTimer = setTimeout(() => {
      flushTimer = null
      void flush()
    }, LIVE_COALESCE_MS)
  }

  async function flush(): Promise<void> {
    const ids = [...pending]
    pending.clear()
    if (ids.length === 0) return

    let rows: T[]
    try {
      rows = await options.fetchByIds(ids)
    } catch {
      // Transient failure; the next signal (or a reconnect) retries.
      return
    }

    const found = new Set(rows.map((row) => row.id))
    for (const row of rows) {
      const index = options.items.value.findIndex((item) => item.id === row.id)
      if (index !== -1) options.items.value[index] = row
    }

    // A requested id missing from the response means the row left the
    // filtered set (a field it's grouped/filtered on changed); position
    // under the current sort/pagination is unknowable client-side, so
    // fall back to a full refresh rather than guessing.
    if (ids.some((id) => !found.has(id))) {
      options.onFullRefresh()
    }
  }

  function handleSignal(signal: LiveSignal): void {
    switch (signal.action) {
      case 'deleted': {
        const index = options.items.value.findIndex((item) => item.id === signal.id)
        if (index !== -1) {
          options.items.value.splice(index, 1)
          options.total.value = Math.max(0, options.total.value - 1)
        }
        break
      }
      case 'created':
      case 'bulk':
        options.onFullRefresh()
        break
      case 'updated': {
        // The big win: a table showing 25 of 5000 rows discards ~99.5% of
        // signals with zero network call.
        const isVisible = options.items.value.some((item) => item.id === signal.id)
        if (!isVisible) return
        pending.add(signal.id)
        scheduleFlush()
        break
      }
    }
  }

  const unsubscribe = live.on(options.resource, handleSignal)

  // Recovery for whatever was missed while disconnected.
  watch(
    () => live.reconnectCount,
    () => options.onFullRefresh(),
  )

  onScopeDispose(() => {
    unsubscribe()
    if (flushTimer) {
      clearTimeout(flushTimer)
      flushTimer = null
    }
  })
}
