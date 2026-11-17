import { webApi } from '@/core/api/webRequest'

import type { BoughtItemCreateRequest } from '../types/boughtItemsRequest'
import type { BoughtItemResponse } from '../types/boughtItemsResponse'

export async function createBoughtItem(
  payload: BoughtItemCreateRequest,
): Promise<BoughtItemResponse> {
  return webApi.post('/bought-items/', { body: payload })
}
