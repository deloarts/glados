import { storeToRefs } from 'pinia'

import { useMadeItemsCatalogueFiltersStore } from '../stores/madeItemsCatalogueFiltersStore'
import {
  useMadeItemsCatalogueViewStore,
  useMadeItemsShowAllRevisionsStore,
} from '../stores/madeItemsCatalogueViewStore'
import { toDateRangeFilterParams, toMadeItemFilterParams } from '../stores/madeItemsCatalogueColumnsStore'

import type { MadeItemFilterParams } from '../types/madeItemsRequest'

/**
 * The catalogue's current search, column filters, sort, revision and
 * archived toggles as list query params without the page window. The table
 * and the export both read the list through it, so an export holds exactly
 * the rows the table filters to, in the same order.
 */
export function useMadeItemsCatalogueQuery(): () => Omit<MadeItemFilterParams, 'skip' | 'limit'> {
  const { filters, dateRangeFilters, search, showArchived } = storeToRefs(
    useMadeItemsCatalogueFiltersStore(),
  )
  const { sortBy, sortDir } = storeToRefs(useMadeItemsCatalogueViewStore())
  const showAllRevisionsStore = useMadeItemsShowAllRevisionsStore()

  return () => ({
    ...(search.value ? { search: search.value } : {}),
    ...toMadeItemFilterParams(filters.value),
    ...toDateRangeFilterParams(dateRangeFilters.value),
    ...(sortBy.value ? { order_by: sortBy.value, order_dir: sortDir.value } : {}),
    latest_only: !showAllRevisionsStore.showAllRevisions,
    ...(showArchived.value ? { include_archived: true } : {}),
  })
}
