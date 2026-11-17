import { reactive } from 'vue'

import { getLotsByIds } from '../api/getLotsByIds'

const cache = reactive<Record<number, string>>({})
const pending = new Set<number>()

// Ids requested since the last flush. `ensureLoaded` enqueues here instead
// of firing a request per id; a microtask flush drains the queue into one
// batched GET /production-lots?ids=... request, so N callers in the same
// tick (e.g. a demands table rendering N rows) produce exactly one call.
let queuedIds: number[] = []
let flushScheduled = false

function flush(): void {
  flushScheduled = false
  const ids = queuedIds
  queuedIds = []
  if (ids.length === 0) return

  // A failed batch leaves its ids uncached, so they keep the `#id` fallback
  // and the next ensureLoaded() asks again.
  getLotsByIds(ids)
    .then((lots) => {
      for (const lot of lots) {
        cache[lot.id] = lot.lot_number
      }
    })
    .catch(() => {})
    .finally(() => {
      for (const id of ids) pending.delete(id)
    })
}

function scheduleFlush(): void {
  if (flushScheduled) return
  flushScheduled = true
  queueMicrotask(flush)
}

// Test-only escape hatch: cache/pending/queue are module-level (shared
// across every useLotNumberCache() call) so state otherwise leaks between
// specs.
export function __resetLotNumberCache(): void {
  for (const key of Object.keys(cache)) delete cache[Number(key)]
  pending.clear()
  queuedIds = []
  flushScheduled = false
}

export function useLotNumberCache() {
  function lotNumber(id: number): string {
    return cache[id] ?? `#${id}`
  }

  function ensureLoaded(id: number): void {
    if (id in cache || pending.has(id)) return
    pending.add(id)
    queuedIds.push(id)
    scheduleFlush()
  }

  return { lotNumber, ensureLoaded }
}
