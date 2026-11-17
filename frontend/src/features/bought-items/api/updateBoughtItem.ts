import { webApi } from '@/core/api/webRequest'

import type { BoughtItemUpdateRequest } from '../types/boughtItemsRequest'
import type { BoughtItemResponse } from '../types/boughtItemsResponse'

export async function updateBoughtItem(
  itemId: number,
  payload: BoughtItemUpdateRequest,
): Promise<BoughtItemResponse> {
  return webApi.put('/bought-items/{item_id}', { path: { item_id: itemId }, body: payload })
}
