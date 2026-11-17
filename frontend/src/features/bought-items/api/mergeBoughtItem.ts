import { webApi } from '@/core/api/webRequest'

import type { BoughtItemResponse } from '../types/boughtItemsResponse'

export async function mergeBoughtItem(
  sourceId: number,
  targetId: number,
): Promise<BoughtItemResponse> {
  return webApi.post('/bought-items/{item_id}/merge', {
    path: { item_id: sourceId },
    body: {
      target_id: targetId,
    },
  })
}
