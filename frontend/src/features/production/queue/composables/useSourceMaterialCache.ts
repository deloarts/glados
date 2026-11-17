import { ref } from 'vue'

import { sourceItemsApi } from '@/features/source-items'
import type { SourceItemResponse } from '@/features/source-items'

// Module-scope cache of source items by id, shared by every caller.
const cache = ref(new Map<number, SourceItemResponse>())
const pending = new Set<number>()

export function useSourceMaterialCache() {
  // Returns the cached item or null and starts a background fetch that
  // fills the cache. A failed fetch leaves the id uncached, so the caller
  // keeps showing nothing and the next resolve() asks again.
  function resolve(sourceItemId: number | null): SourceItemResponse | null {
    if (sourceItemId === null) return null
    const cached = cache.value.get(sourceItemId)
    if (cached) return cached
    if (!pending.has(sourceItemId)) {
      pending.add(sourceItemId)
      sourceItemsApi
        .list({ id: sourceItemId, limit: 1 })
        .then((page) => {
          const item = page.items[0]
          if (item) cache.value.set(sourceItemId, item)
        })
        .catch(() => {})
        .finally(() => pending.delete(sourceItemId))
    }
    return null
  }

  return { resolve }
}
