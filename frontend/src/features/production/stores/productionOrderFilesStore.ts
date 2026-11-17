import { createFilesStore } from '@/core/stores/createFilesStore'

import { getProductionOrderFiles } from '../api/getProductionOrderFiles'
import { uploadProductionOrderFile } from '../api/uploadProductionOrderFile'
import { deleteProductionOrderFile } from '../api/deleteProductionOrderFile'
import type { ProductionOrderFile, ProductionOrderFileCategory } from '../types/productionOrdersResponse'

// No getForItems: production orders have no bulk file endpoint (mirrors
// orderFilesStore.ts), so the store falls back to one request per id.
export const useProductionOrderFilesStore = createFilesStore<
  ProductionOrderFile,
  ProductionOrderFileCategory
>('productionOrderFiles', {
  getForItem: getProductionOrderFiles,
  upload: uploadProductionOrderFile,
  remove: deleteProductionOrderFile,
  itemIdOf: (file) => file.production_order_id,
  // measurement_report accumulates: a lab can attach more than one report
  // to the same completion.
  singletonCategories: [],
})
