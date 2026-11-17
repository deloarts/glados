import { createCatalogueViewStore } from '@/shared/stores/createCatalogueViewStore'

import type { BoughtItemSortBy } from '../types/boughtItemsRequest'

export type BoughtItemGroupBy = 'manufacturer_name' | 'article_groups' | null

export const useBoughtItemsCatalogueViewStore = createCatalogueViewStore<
  'manufacturer_name' | 'article_groups',
  BoughtItemSortBy
>('boughtItemsCatalogueView')
