import { createCatalogueFiltersStore } from '@/shared/stores/createCatalogueFiltersStore'

import {
  createEmptyMadeItemFilters,
  createEmptyDateRangeFilters,
} from './madeItemsCatalogueColumnsStore'

export const useMadeItemsCatalogueFiltersStore = createCatalogueFiltersStore(
  'madeItemsCatalogueFilters',
  createEmptyMadeItemFilters,
  createEmptyDateRangeFilters,
)
