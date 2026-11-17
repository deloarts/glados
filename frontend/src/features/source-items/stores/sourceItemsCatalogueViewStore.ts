import { createCatalogueViewStore } from '@/shared/stores/createCatalogueViewStore'

import type { SourceItemSortBy } from '../types/sourceItemsRequest'

export type SourceItemGroupBy = 'manufacturer_name' | 'status' | null

export const useSourceItemsCatalogueViewStore = createCatalogueViewStore<
  'manufacturer_name' | 'status',
  SourceItemSortBy
>('sourceItemsCatalogueView')
