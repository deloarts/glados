import { createCatalogueFiltersStore } from '@/shared/stores/createCatalogueFiltersStore'

import {
  createEmptySourceItemFilters,
  createEmptyDateRangeFilters,
} from './sourceItemsCatalogueColumnsStore'

export const useSourceItemsCatalogueFiltersStore = createCatalogueFiltersStore(
  'sourceItemsCatalogueFilters',
  createEmptySourceItemFilters,
  createEmptyDateRangeFilters,
)
