/** The documents of a supplier's offer on a quote request, from the shared files factory. */
import { createOwnerFilesApi } from '@/shared/api/createFilesApi'

import type { QuoteFileCategory, QuoteRequestFile } from '../types/quoteRequestsResponse'

export const offerFilesApi = createOwnerFilesApi<{
  file: QuoteRequestFile
  category: QuoteFileCategory
}>('quoteSupplier')
