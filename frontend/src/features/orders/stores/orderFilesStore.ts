import { createFilesStore } from '@/core/stores/createFilesStore'

import { getOrderFiles } from '../api/getOrderFiles'
import { uploadOrderAttachment } from '../api/uploadOrderAttachment'
import { deleteOrderAttachment } from '../api/deleteOrderAttachment'
import type { OrderFile, OrderFileCategory } from '../types/ordersResponse'

// No getForItems: orders have no bulk file endpoint, and unlike the item
// catalogues nothing renders a thumbnail per row for them. The store falls
// back to one request per id.
export const useOrderFilesStore = createFilesStore<OrderFile, OrderFileCategory>('orderFiles', {
  getForItem: getOrderFiles,
  upload: uploadOrderAttachment,
  remove: deleteOrderAttachment,
  itemIdOf: (file) => file.order_id,
  // Every order file category accumulates; none replaces in place.
  singletonCategories: [],
})
