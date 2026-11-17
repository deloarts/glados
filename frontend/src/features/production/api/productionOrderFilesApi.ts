/** Production order file attachments, built from the shared files factory. */
import { createOwnerFilesApi } from '@/shared/api/createFilesApi'

import type {
  ProductionOrderFile,
  ProductionOrderFileCategory,
} from '../types/productionOrdersResponse'

export const productionOrderFilesApi = createOwnerFilesApi<{
  file: ProductionOrderFile
  category: ProductionOrderFileCategory
}>('productionOrder')
