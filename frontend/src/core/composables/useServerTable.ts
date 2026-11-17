import { onMounted, ref } from 'vue'
import { useDebounceFn } from '@vueuse/core'

import { TABLE_DEBOUNCE_MS, TABLE_DEFAULT_ROWS } from '@/core/constants/table'

import type { DataTablePageEvent } from 'openvue/datatable'

/**
 * The pagination/fetch-trigger plumbing every server-paginated `<DataTable
 * lazy>` repeats by hand: `first`/`rows` state, a debounced fetch for
 * typed filters, an immediate fetch for paging, and the initial
 * `onMounted` load. What's deliberately left to the caller is *which*
 * reactive sources (search, column filters, sort, an external
 * refresh-trigger…) should call `resetAndFetch`/`resetAndFetchDebounced`/
 * `fetchItems` and how they're grouped, that varies per table and is
 * exactly what a plain `watch(...)` call already expresses well; wrapping
 * it here would either lose the ability to batch sources (e.g. `watch([sortBy,
 * sortDir], ...)` firing once) or need generic-typing gymnastics for no
 * real gain.
 *
 * `fetch` is expected to own its own request sequencing (see
 * `useSequencedFetch`; a store's `refresh()` built on it is the intended
 * `fetch` here), so a slow page 1 response can't clobber a fast page 2 one.
 */
export function useServerTable<TParams>(options: {
  // Takes the current page state as an argument (rather than the caller
  // closing over `first`/`rows` refs directly) because those refs are
  // owned by, and only exist once returned from, this composable itself.
  fetchParams: (page: { first: number; rows: number }) => TParams
  fetch: (params: TParams) => Promise<void> | void
  debounceMs?: number
}) {
  const first = ref(0)
  const rows = ref(TABLE_DEFAULT_ROWS)

  function fetchItems(): void {
    void options.fetch(options.fetchParams({ first: first.value, rows: rows.value }))
  }

  const debouncedFetchItems = useDebounceFn(fetchItems, options.debounceMs ?? TABLE_DEBOUNCE_MS)

  function resetAndFetch(): void {
    first.value = 0
    fetchItems()
  }

  function resetAndFetchDebounced(): void {
    first.value = 0
    void debouncedFetchItems()
  }

  function onPage(event: DataTablePageEvent): void {
    first.value = event.first
    rows.value = event.rows
    fetchItems()
  }

  onMounted(fetchItems)

  return {
    first,
    rows,
    fetchItems,
    debouncedFetchItems,
    resetAndFetch,
    resetAndFetchDebounced,
    onPage,
    // Row-filter `@filter` events are debounced by convention, because the
    // typed text/number filters fire on every keystroke.
    onFilter: resetAndFetchDebounced,
  }
}
