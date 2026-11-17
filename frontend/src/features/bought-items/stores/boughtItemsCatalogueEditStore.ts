import { createCatalogueEditStore } from '@/shared/stores/createCatalogueEditStore'

import type { BoughtItemResponse } from '../types/boughtItemsResponse'

export const useBoughtItemsCatalogueEditStore = createCatalogueEditStore<BoughtItemResponse>(
  'boughtItemsCatalogueEdit',
)
