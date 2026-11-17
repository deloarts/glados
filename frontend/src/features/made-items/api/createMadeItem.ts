import { webApi } from '@/core/api/webRequest'

import type { MadeItemCreateRequest } from '../types/madeItemsRequest'
import type { MadeItemResponse } from '../types/madeItemsResponse'

export async function createMadeItem(payload: MadeItemCreateRequest): Promise<MadeItemResponse> {
  // processes are refined to the role union, see MadeItemProcessResponse.
  return webApi.post('/made-items/', { body: payload }) as Promise<MadeItemResponse>
}
