import { ref, watch } from 'vue'
import type { Ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import type { ChangelogEntry } from '@/shared/utils/changelog'

/** What `ItemChangelogDialog` reads from and calls on a changelog store. */
export interface ItemChangelogStore<TItem> {
  loading: boolean
  entries: ChangelogEntry[]
  select: (item: TItem | null) => void
  clear: () => void
}

/**
 * Builds the changelog store behind a catalogue's changelog dialog. Setting
 * `selectedItem` loads that item's entries through `fetch`, and `clear()`
 * resets the store when the dialog closes.
 */
export function createItemChangelogStore<TItem extends { id: number }>(
  id: string,
  fetch: (itemId: number) => Promise<ChangelogEntry[]>,
) {
  return defineStore(id, () => {
    const { loading, error, run } = useSequencedFetch(fetch)
    const selectedItem = ref(null) as Ref<TItem | null>
    const entries = ref<ChangelogEntry[]>([])

    // ── Internal ─────────────────────────────────────────────────────────

    // run() drops failures into error and discards out-of-order responses.
    watch(selectedItem, async (item) => {
      entries.value = []

      if (!item) return

      const result = await run(item.id)
      if (result) entries.value = result
    })

    function select(item: TItem | null): void {
      selectedItem.value = item
    }

    function clear(): void {
      selectedItem.value = null
      entries.value = []
    }

    return {
      loading,
      error,
      selectedItem,
      entries,

      select,
      clear,
    }
  })
}
