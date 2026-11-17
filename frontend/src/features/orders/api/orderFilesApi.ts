/** Order file attachments, built from the shared files factory. */
import { createOwnerFilesApi } from '@/shared/api/createFilesApi'

import type { OrderFile, OrderFileCategory } from '../types/ordersResponse'

export const orderFilesApi = createOwnerFilesApi<{ file: OrderFile; category: OrderFileCategory }>(
  'order',
)
