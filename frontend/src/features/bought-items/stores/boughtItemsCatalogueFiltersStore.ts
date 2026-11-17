import { createCatalogueFiltersStore } from '@/shared/stores/createCatalogueFiltersStore'

import {
  createEmptyBoughtItemFilters,
  createEmptyDateRangeFilters,
} from './boughtItemsCatalogueColumnsStore'

export const useBoughtItemsCatalogueFiltersStore = createCatalogueFiltersStore(
  'boughtItemsCatalogueFilters',
  createEmptyBoughtItemFilters,
  createEmptyDateRangeFilters,
)
