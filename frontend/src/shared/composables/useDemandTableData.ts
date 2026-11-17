import { watch } from 'vue'
import type { Ref, WatchSource } from 'vue'

import { useServerTable } from '@/core/composables/useServerTable'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useLiveRows } from '@/core/realtime/useLiveRows'
import { useUsersStore } from '@/core/stores/usersStore'
import type { FilterSortDir } from '@/shared/stores/createFiltersStore'

/**
 * Paging and sort params the demand list endpoints take on top of their
 * filters. `order_by`/`order_dir` are only sent while a sort is set.
 */
export interface DemandPageParams<TSortField extends string> {
  skip: number
  limit: number
  order_by?: TSortField
  order_dir?: FilterSortDir
}

export interface DemandTableDataOptions<
  TRow extends { id: number },
  TFilters extends object,
  TSortField extends string,
> {
  /** The demands store's `items`/`total`, as refs from `storeToRefs`. */
  items: Ref<TRow[]>
  total: Ref<number>
  loading: () => boolean
  /**
   * The table's filters only, without paging or sort. The page fetch and
   * the live-row refetch both apply them.
   */
  filterParams: () => TFilters
  sortBy: Ref<TSortField | null>
  sortDir: Ref<FilterSortDir>
  /** Loads one page into the demands store, normally its `refresh()`. */
  fetchPage: (params: DemandPageParams<TSortField> & TFilters) => Promise<void>
  /**
   * The kind's demand list call, used to refetch single rows on a live
   * signal.
   */
  fetchByIds: (params: TFilters & { ids: number[] }) => Promise<{ items: TRow[] }>
  /** Loads the allocation summaries shown per row. */
  fetchSummaries: (ids: number[]) => Promise<unknown>
  /** LiveResource value the table subscribes to. */
  liveResource: string
  /** Store counters other components bump to make the table refetch. */
  refreshTriggers: WatchSource[]
  /**
   * When given, selected rows are replaced by their fresh copies whenever
   * the list changes, so panels working on the selection never act on a
   * stale snapshot.
   */
  selection?: { get: () => TRow[]; set: (rows: TRow[]) => void }
}

/**
 * Loading plumbing shared by the bought, made and source item demand
 * tables: server paging through useServerTable, the allocation summaries
 * and the users list behind the creator filter, live row sync, refetching
 * on sort changes and refresh triggers, and the loading bar. Which filters
 * refetch immediately and which are debounced stays with each table,
 * because the filters differ per kind.
 */
export function useDemandTableData<
  TRow extends { id: number },
  TFilters extends object,
  TSortField extends string,
>(options: DemandTableDataOptions<TRow, TFilters, TSortField>) {
  const usersStore = useUsersStore()

  watchLoadingBar(options.loading)

  const serverTable = useServerTable({
    fetchParams: ({ first, rows }) => ({
      skip: first,
      limit: rows,
      ...options.filterParams(),
      ...(options.sortBy.value
        ? { order_by: options.sortBy.value, order_dir: options.sortDir.value }
        : {}),
    }),
    fetch: async (params) => {
      await options.fetchPage(params)

      const ids = options.items.value.map((d) => d.id)
      if (ids.length > 0) {
        void options.fetchSummaries(ids)
      }
      void usersStore.ensureLoaded()
    },
  })
  const { fetchItems, resetAndFetch } = serverTable

  useLiveRows<TRow>({
    resource: options.liveResource,
    items: options.items,
    total: options.total,
    fetchByIds: async (ids) => {
      // Allocating or deallocating a demand signals the demand row itself,
      // but the summary shown per row lives in a separate store keyed by
      // demand id, so refreshing only the row would leave it stale.
      const [response] = await Promise.all([
        options.fetchByIds({ ...options.filterParams(), ids }),
        options.fetchSummaries(ids),
      ])
      return response.items
    },
    onFullRefresh: fetchItems,
  })

  watch([options.sortBy, options.sortDir], resetAndFetch)

  watch(options.refreshTriggers, () => fetchItems())

  const selection = options.selection
  if (selection) {
    // Deep because replaceItem() and the live-sync flush patch rows by index
    // or splice them in place instead of reassigning the array.
    watch(
      options.items,
      (items) => {
        if (selection.get().length === 0) return
        const byId = new Map(items.map((item) => [item.id, item]))
        selection.set(selection.get().map((d) => byId.get(d.id) ?? d))
      },
      { deep: true },
    )
  }

  return serverTable
}
