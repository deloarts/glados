/** Product file attachments, built from the shared files factory. */
import { createFilesApi } from '@/shared/api/createFilesApi'

import type { ProductFile, ProductFileCategory } from '../types/productResponse'

export const productFilesApi = createFilesApi<{ file: ProductFile; category: ProductFileCategory }>(
  'product',
)
