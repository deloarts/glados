import { computed, ref } from 'vue'
import type { ComputedRef, Ref } from 'vue'
import { defineStore } from 'pinia'
import { FilterMatchMode } from '@openvue/core/api'
import type { DataTableFilterMeta } from 'openvue/datatable'

import type { PageResponse } from '@/core/api/types'
import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { filterMetaValue, hasActiveFilterMeta } from '@/core/utils/filterMeta'
import { dateToParam } from '@/core/utils/dates'
import type { ListPlaceTarget } from '@/shared/types/listOrder'

/**
 * The query params every archivable master-data list endpoint shares. Each
 * kind's own `*FilterParams` aliases its route's generated query, which adds
 * the column filters on top and types an omitted value as null.
 */
export interface MasterDataListParams {
  skip?: number | null
  limit?: number | null
  search?: string | null
  order_by?: string | null
  order_dir?: string | null
  include_archived?: boolean
}

/**
 * How one column filter is matched in the table and sent to the backend.
 * `contains` and `equals` are sent only when truthy. `boolean` is sent
 * whenever it is set, so a `false` filter still narrows the list.
 */
export type MasterDataFilterKind = 'contains' | 'equals' | 'boolean'

type SortBy<TParams extends MasterDataListParams> = NonNullable<TParams['order_by']>
type SortDir<TParams extends MasterDataListParams> = NonNullable<TParams['order_dir']>

type DateRangeRefs<TDateRange extends string> = {
  [K in TDateRange as `${K}From` | `${K}To`]: Ref<Date | null>
}

export interface MasterDataApi<TItem, TParams, TCreate, TUpdate> {
  list: (params?: TParams) => Promise<PageResponse<TItem>>
  create: (payload: TCreate) => Promise<TItem>
  update: (id: number, payload: TUpdate) => Promise<TItem>
  archive: (id: number) => Promise<TItem>
  restore: (id: number) => Promise<TItem>
  /** For a hand-ordered kind: puts an entry next to a neighbour, as a drag does. */
  place?: (id: number, target: ListPlaceTarget) => Promise<void>
}

export type MasterDataStoreBase<
  TItem extends { id: number },
  TParams extends MasterDataListParams,
  TCreate,
  TUpdate,
  TDateRange extends string,
> = {
  loading: ComputedRef<boolean>
  error: ComputedRef<string | null>
  /** True while a create, update, archive or restore request is in flight. */
  mutating: Ref<boolean>
  /**
   * The complete list other features read for pickers, archived rows
   * included. With `tableOnly` it is the management table's current page.
   */
  items: Ref<TItem[]>
  /**
   * The management table's current page, kept apart from `items` so paging
   * the table never shrinks what pickers elsewhere see. With `tableOnly` it
   * is the same list as `items`.
   */
  tableItems: Ref<TItem[]>
  total: Ref<number>
  filters: Ref<DataTableFilterMeta>
  clearTrigger: Ref<number>
  refreshTrigger: Ref<number>
  search: Ref<string>
  showActions: Ref<boolean>
  sortBy: Ref<SortBy<TParams> | null>
  sortDir: Ref<SortDir<TParams>>
  showArchived: Ref<boolean>
  hasActiveFilters: ComputedRef<boolean>
  /**
   * True while the table shows the hand-kept order: no sort, search,
   * column filter or date range, so a row's neighbours on screen are its
   * neighbours in that order. Showing archived rows keeps it.
   */
  manualOrder: ComputedRef<boolean>
  /**
   * The picker-list row with that id, through a map rebuilt whenever
   * `items` changes. Accepts an unset id, which finds nothing.
   */
  getById: (id: number | null | undefined) => TItem | undefined
  /**
   * The table's query params from its search, column filters, date ranges,
   * archived toggle and sort, plus the page when one is given.
   */
  buildParams: (page?: { skip: number; limit: number }) => TParams
  refresh: (params?: TParams) => Promise<void>
  refreshTable: (page?: { skip: number; limit: number }) => Promise<void>
  triggerRefresh: () => void
  toggleShowActions: () => void
  setSort: (field: SortBy<TParams>, dir: SortDir<TParams>) => void
  clearSort: () => void
  toggleShowArchived: () => void
  clearAll: () => void
  create: (payload: TCreate) => Promise<TItem>
  update: (id: number, payload: TUpdate) => Promise<TItem>
  archive: (id: number) => Promise<void>
  restore: (id: number) => Promise<void>
  /**
   * Puts an entry next to a neighbour, as dragging its row does. The page
   * shown after the drop, when given, replaces the table page at once, so
   * the row stays where it was dropped while the refetch runs. Only for a
   * kind whose `api` has `place`.
   */
  place: (id: number, target: ListPlaceTarget, droppedPage?: TItem[]) => Promise<void>
} & DateRangeRefs<TDateRange>

export interface CreateMasterDataStoreConfig<
  TItem extends { id: number },
  TParams extends MasterDataListParams,
  TCreate,
  TUpdate,
  TDateRange extends string,
  TExtra extends Record<string, unknown>,
> {
  api: MasterDataApi<TItem, TParams, TCreate, TUpdate>
  /**
   * Column filters in table order. Each key is both the DataTable filter
   * field and the backend query param it is sent as.
   */
  filters: Record<string, MasterDataFilterKind>
  /**
   * Date ranges filtered outside the DataTable filter meta, because a range
   * is two bounds (see useDateRangeFilter). `'created'` yields the
   * `createdFrom`/`createdTo` refs sent as `created_from`/`created_to`.
   */
  dateRanges?: readonly TDateRange[]
  /**
   * For a kind no other feature picks from, so the store keeps no separate
   * picker list. `items` and `tableItems` are then one list, the management
   * table's current page: `refresh(params)` sends `params` exactly as given
   * and stores the page in `items` and `total`, `refreshTable` fetches the
   * built table params through it, and `create` leaves the page alone, since
   * the refetch it triggers decides where the new row goes.
   */
  tableOnly?: boolean
  /**
   * Adds kind-specific state, getters and actions on top of the shared
   * bundle. Runs inside the store's setup, so it may use `ref`, `computed`
   * and `watch`, and it may read the shared refs through `base`.
   */
  extend?: (base: MasterDataStoreBase<TItem, TParams, TCreate, TUpdate, TDateRange>) => TExtra
}

function createEmptyFilters(fields: Record<string, MasterDataFilterKind>): DataTableFilterMeta {
  const meta: DataTableFilterMeta = {}
  for (const [field, kind] of Object.entries(fields)) {
    meta[field] = {
      value: null,
      matchMode: kind === 'contains' ? FilterMatchMode.CONTAINS : FilterMatchMode.EQUALS,
    }
  }
  return meta
}

/**
 * Builds the Pinia store behind an archivable master-data management page
 * (suppliers, customers, products, ...): a picker list in `items` that always
 * includes archived rows, a paginated, filtered and sorted management table
 * in `tableItems`, and create/update/archive/restore actions that patch
 * `items` in place and bump `refreshTrigger` so the table refetches.
 *
 * The picker and the table fetch through two independent sequenced trackers
 * because they are unrelated requests to the same endpoint. Sharing one
 * tracker would let a table page fetch discard an in-flight picker fetch as
 * superseded, or the other way round.
 */
export function createMasterDataStore<
  TItem extends { id: number },
  TParams extends MasterDataListParams,
  TCreate,
  TUpdate,
  TDateRange extends string = never,
  TExtra extends Record<string, unknown> = Record<never, never>,
>(
  id: string,
  config: CreateMasterDataStoreConfig<TItem, TParams, TCreate, TUpdate, TDateRange, TExtra>,
) {
  type Base = MasterDataStoreBase<TItem, TParams, TCreate, TUpdate, TDateRange>

  return defineStore(id, (): Base & TExtra => {
    const { api } = config
    const tableOnly = config.tableOnly ?? false

    const pickerFetch = useSequencedFetch(api.list)
    const tableFetch = useSequencedFetch(api.list)
    const loading = computed(() => pickerFetch.loading.value || tableFetch.loading.value)
    const error = computed(() => pickerFetch.error.value ?? tableFetch.error.value)
    const mutating = ref(false)
    const items = ref([]) as Ref<TItem[]>
    const tableItems = tableOnly ? items : (ref([]) as Ref<TItem[]>)
    const total = ref(0)
    const filters = ref<DataTableFilterMeta>(createEmptyFilters(config.filters))
    const clearTrigger = ref(0)
    const refreshTrigger = ref(0)
    const search = ref('')
    const showActions = ref(false)
    const sortBy = ref(null) as Ref<SortBy<TParams> | null>
    const sortDir = ref('asc') as Ref<SortDir<TParams>>
    const showArchived = ref(false)

    const dateRanges = config.dateRanges ?? []
    const dateRefs: Record<string, Ref<Date | null>> = {}
    for (const range of dateRanges) {
      dateRefs[`${range}From`] = ref<Date | null>(null)
      dateRefs[`${range}To`] = ref<Date | null>(null)
    }

    const hasActiveFilters = computed<boolean>(() => {
      if (search.value !== '') return true
      if (showArchived.value) return true
      if (Object.values(dateRefs).some((r) => r.value !== null)) return true
      return hasActiveFilterMeta(filters.value)
    })

    const manualOrder = computed<boolean>(
      () =>
        sortBy.value === null &&
        search.value === '' &&
        !Object.values(dateRefs).some((r) => r.value !== null) &&
        !hasActiveFilterMeta(filters.value),
    )

    const itemsById = computed(() => new Map(items.value.map((item) => [item.id, item])))

    function getById(itemId: number | null | undefined): TItem | undefined {
      return itemId == null ? undefined : itemsById.value.get(itemId)
    }

    function buildParams(page?: { skip: number; limit: number }): TParams {
      const params: Record<string, unknown> = {}

      if (search.value) params.search = search.value

      for (const [field, kind] of Object.entries(config.filters)) {
        const value = filterMetaValue(filters.value, field)
        const send = kind === 'boolean' ? value !== null && value !== undefined : Boolean(value)
        if (send) params[field] = value
      }

      for (const range of dateRanges) {
        const from = dateRefs[`${range}From`]?.value
        const to = dateRefs[`${range}To`]?.value
        if (from) params[`${range}_from`] = dateToParam(from) ?? undefined
        if (to) params[`${range}_to`] = dateToParam(to) ?? undefined
      }

      if (showArchived.value) params.include_archived = true

      if (sortBy.value) {
        params.order_by = sortBy.value
        params.order_dir = sortDir.value
      }

      if (page) {
        params.skip = page.skip
        params.limit = page.limit
      }

      return params as TParams
    }

    // Always includes archived rows, regardless of the table's own "Show
    // archived" toggle, because referencing an already-archived row is
    // allowed and pickers render it distinctly (see useArchivableOptions.ts).
    // The table's search, column filters and sort never narrow this list.
    async function refresh(params?: TParams): Promise<void> {
      if (tableOnly) {
        const response = await tableFetch.run(params)
        if (!response) return

        items.value = response.items
        total.value = response.total
        return
      }

      const response = await pickerFetch.run({ ...params, include_archived: true } as TParams)
      if (!response) return

      items.value = response.items
    }

    async function refreshTable(page?: { skip: number; limit: number }): Promise<void> {
      if (tableOnly) return refresh(buildParams(page))

      const response = await tableFetch.run(buildParams(page))
      if (!response) return

      tableItems.value = response.items
      total.value = response.total
    }

    function triggerRefresh(): void {
      refreshTrigger.value++
    }

    function toggleShowActions(): void {
      showActions.value = !showActions.value
    }

    function setSort(field: SortBy<TParams>, dir: SortDir<TParams>): void {
      sortBy.value = field
      sortDir.value = dir
    }

    function clearSort(): void {
      sortBy.value = null
      sortDir.value = 'asc' as SortDir<TParams>
    }

    function toggleShowArchived(): void {
      showArchived.value = !showArchived.value
    }

    function clearAll(): void {
      filters.value = createEmptyFilters(config.filters)
      search.value = ''
      showArchived.value = false
      for (const r of Object.values(dateRefs)) r.value = null
      clearTrigger.value++
    }

    function replaceItem(itemId: number, updated: TItem): void {
      const index = items.value.findIndex((item) => item.id === itemId)
      if (index !== -1) items.value[index] = updated
    }

    async function mutate<TResult>(request: () => Promise<TResult>): Promise<TResult> {
      mutating.value = true
      try {
        return await request()
      } finally {
        mutating.value = false
      }
    }

    function create(payload: TCreate): Promise<TItem> {
      return mutate(async () => {
        const created = await api.create(payload)
        if (!tableOnly) items.value.push(created)
        triggerRefresh()
        return created
      })
    }

    function update(itemId: number, payload: TUpdate): Promise<TItem> {
      return mutate(async () => {
        const updated = await api.update(itemId, payload)
        replaceItem(itemId, updated)
        triggerRefresh()
        return updated
      })
    }

    function archive(itemId: number): Promise<void> {
      return mutate(async () => {
        replaceItem(itemId, await api.archive(itemId))
        triggerRefresh()
      })
    }

    function restore(itemId: number): Promise<void> {
      return mutate(async () => {
        replaceItem(itemId, await api.restore(itemId))
        triggerRefresh()
      })
    }

    function place(itemId: number, target: ListPlaceTarget, droppedPage?: TItem[]): Promise<void> {
      const request = api.place
      if (!request) return Promise.reject(new Error(`${id} cannot place an entry.`))
      if (droppedPage) tableItems.value = droppedPage
      return mutate(async () => {
        try {
          await request(itemId, target)
          if (!tableOnly) await refresh()
        } finally {
          // Also after a failure, so the table drops the optimistic order.
          triggerRefresh()
        }
      })
    }

    const base = {
      loading,
      error,
      mutating,
      items,
      tableItems,
      total,
      filters,
      clearTrigger,
      refreshTrigger,
      search,
      showActions,
      sortBy,
      sortDir,
      showArchived,
      ...dateRefs,
      hasActiveFilters,
      manualOrder,
      getById,
      buildParams,
      refresh,
      refreshTable,
      triggerRefresh,
      toggleShowActions,
      setSort,
      clearSort,
      toggleShowArchived,
      clearAll,
      create,
      update,
      archive,
      restore,
      place,
    } as Base

    const extra = config.extend?.(base) ?? ({} as TExtra)

    return { ...base, ...extra }
  })
}

/**
 * A table grouping that toggles off when the active group is picked again.
 * Spread from `extend` by the master-data stores whose tables group rows;
 * the shared `clearAll` leaves it alone, as grouping is not a filter.
 */
export function useToggleGroupBy<TGroupBy extends string>() {
  const groupBy = ref(null) as Ref<TGroupBy | null>

  function setGroupBy(value: TGroupBy): void {
    groupBy.value = groupBy.value === value ? null : value
  }

  function clearGroupBy(): void {
    groupBy.value = null
  }

  return { groupBy, setGroupBy, clearGroupBy }
}
