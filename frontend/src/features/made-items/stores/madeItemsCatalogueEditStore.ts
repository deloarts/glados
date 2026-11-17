import { createCatalogueEditStore } from '@/shared/stores/createCatalogueEditStore'

import type { MadeItemResponse } from '../types/madeItemsResponse'

export const useMadeItemsCatalogueEditStore =
  createCatalogueEditStore<MadeItemResponse>('madeItemsCatalogueEdit')
