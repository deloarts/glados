import { createCatalogueEditStore } from '@/shared/stores/createCatalogueEditStore'

import type { SourceItemResponse } from '../types/sourceItemsResponse'

export const useSourceItemsCatalogueEditStore = createCatalogueEditStore<SourceItemResponse>(
  'sourceItemsCatalogueEdit',
)
