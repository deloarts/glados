import { storeToRefs } from 'pinia'

import { useBoughtItemsCatalogueFiltersStore } from '../stores/boughtItemsCatalogueFiltersStore'
import { useBoughtItemsCatalogueViewStore } from '../stores/boughtItemsCatalogueViewStore'
import { toBoughtItemFilterParams, toDateRangeFilterParams } from '../stores/boughtItemsCatalogueColumnsStore'

import type { BoughtItemFilterParams } from '../types/boughtItemsRequest'

/**
 * The catalogue's current search, column filters, sort and archived toggle
 * as list query params without the page window. The table and the export
 * both read the list through it, so an export holds exactly the rows the
 * table filters to, in the same order.
 */
export function useBoughtItemsCatalogueQuery(): () => Omit<BoughtItemFilterParams, 'skip' | 'limit'> {
  const { filters, dateRangeFilters, search, showArchived } = storeToRefs(
    useBoughtItemsCatalogueFiltersStore(),
  )
  const { sortBy, sortDir } = storeToRefs(useBoughtItemsCatalogueViewStore())

  return () => ({
    ...(search.value ? { search: search.value } : {}),
    ...toBoughtItemFilterParams(filters.value),
    ...toDateRangeFilterParams(dateRangeFilters.value),
    ...(sortBy.value ? { order_by: sortBy.value, order_dir: sortDir.value } : {}),
    ...(showArchived.value ? { include_archived: true } : {}),
  })
}
