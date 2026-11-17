import { createFilesStore } from '@/core/stores/createFilesStore'

import { getProductFiles } from '../api/getProductFiles'
import { getProductFilesForItems } from '../api/getProductFilesForItems'
import { uploadProductFile } from '../api/uploadProductFile'
import { deleteProductFile } from '../api/deleteProductFile'
import { SINGLETON_FILE_CATEGORIES } from '../types/productResponse'
import type { ProductFile, ProductFileCategory } from '../types/productResponse'

export const useProductFilesStore = createFilesStore<ProductFile, ProductFileCategory>(
  'productFiles',
  {
    getForItems: getProductFilesForItems,
    getForItem: getProductFiles,
    upload: uploadProductFile,
    remove: deleteProductFile,
    itemIdOf: (file) => file.product_id,
    singletonCategories: SINGLETON_FILE_CATEGORIES,
  },
)
