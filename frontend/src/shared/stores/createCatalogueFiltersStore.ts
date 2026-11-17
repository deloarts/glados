import type { DataTableFilterMeta } from 'openvue/datatable'

import { hasActiveFilterMeta } from '@/core/utils/filterMeta'
import { createFiltersStore } from './createFiltersStore'
import type { DateRangeFilters } from './createCatalogueColumnsStore'

// A type alias, since createFiltersStore needs an implicit index signature
// that an interface does not get.
export type CatalogueFilterFields = {
  filters: DataTableFilterMeta
  dateRangeFilters: DateRangeFilters
  search: string
  showArchived: boolean
}

/**
 * Builds the filters store of an item catalogue: the column filter model,
 * the date range filters kept beside it, the search text and the archived
 * toggle. The filter objects are mutated in place by the DataTable, so the
 * defaults come from the given factories, and `hasActiveFilters` inspects
 * their values rather than comparing references.
 */
export function createCatalogueFiltersStore(
  id: string,
  createEmptyFilters: () => DataTableFilterMeta,
  createEmptyDateRangeFilters: () => DateRangeFilters,
) {
  return createFiltersStore<CatalogueFilterFields, never, false>(id, {
    defaults: () => ({
      filters: createEmptyFilters(),
      dateRangeFilters: createEmptyDateRangeFilters(),
      search: '',
      showArchived: false,
    }),
    sortable: false,
    isActive: (fields) =>
      hasActiveFilterMeta(fields.filters) ||
      fields.search !== '' ||
      fields.showArchived ||
      Object.values(fields.dateRangeFilters).some(([from, to]) => from !== null || to !== null),
  })
}
