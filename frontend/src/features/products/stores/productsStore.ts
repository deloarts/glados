import { createMasterDataStore, useToggleGroupBy } from '@/shared/stores/createMasterDataStore'
import { archiveProduct } from '../api/archiveProduct'
import { createProduct } from '../api/createProduct'
import { getProducts } from '../api/getProducts'
import { restoreProduct } from '../api/restoreProduct'
import { updateProduct } from '../api/updateProduct'

export type ProductGroupBy = 'customer' | 'is_active' | null

// `items` is read by other features (ProjectFormDialog, ...) as the complete
// product list for pickers.
export const useProductsStore = createMasterDataStore('products', {
  api: {
    list: getProducts,
    create: createProduct,
    update: updateProduct,
    archive: archiveProduct,
    restore: restoreProduct,
  },
  filters: {
    product_number: 'contains',
    customer_id: 'equals',
    is_active: 'boolean',
    description: 'contains',
    designated_user_id: 'equals',
    creator_id: 'equals',
  },
  dateRanges: ['created'],
  extend: () => useToggleGroupBy<Exclude<ProductGroupBy, null>>(),
})
