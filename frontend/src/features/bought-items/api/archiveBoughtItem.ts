import { webApi } from '@/core/api/webRequest'

import type { BoughtItemResponse } from '../types/boughtItemsResponse'

export async function archiveBoughtItem(itemId: number): Promise<BoughtItemResponse> {
  return webApi.post('/bought-items/{item_id}/archive', { path: { item_id: itemId } })
}
