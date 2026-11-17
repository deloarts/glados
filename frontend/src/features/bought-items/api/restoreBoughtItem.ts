import { webApi } from '@/core/api/webRequest'

import type { BoughtItemResponse } from '../types/boughtItemsResponse'

export async function restoreBoughtItem(itemId: number): Promise<BoughtItemResponse> {
  return webApi.post('/bought-items/{item_id}/restore', { path: { item_id: itemId } })
}
