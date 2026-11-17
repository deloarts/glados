import { createFilesStore } from '@/core/stores/createFilesStore'

import { offerFilesApi } from '../api/offerFilesApi'
import type { QuoteFileCategory, QuoteRequestFile } from '../types/quoteRequestsResponse'

// One request per supplier entry; nothing lists the documents of many at once.
export const useOfferFilesStore = createFilesStore<QuoteRequestFile, QuoteFileCategory>(
  'offerFiles',
  {
    getForItem: offerFilesApi.list,
    upload: offerFilesApi.upload,
    remove: offerFilesApi.remove,
    itemIdOf: (file) => file.supplier_row_id,
    // Both categories accumulate.
    singletonCategories: [],
  },
)
