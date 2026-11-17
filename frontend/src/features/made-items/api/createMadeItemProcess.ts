import { webApi } from '@/core/api/webRequest'

import type { MadeItemProcessCreateRequest } from '../types/madeItemsRequest'
import type { MadeItemProcessResponse } from '../types/madeItemsResponse'

export async function createMadeItemProcess(
  itemId: number,
  payload: MadeItemProcessCreateRequest,
): Promise<MadeItemProcessResponse> {
  // The process is refined to the role union, see MadeItemProcessResponse.
  return webApi.post('/made-items/{item_id}/processes', {
    path: { item_id: itemId },
    body: payload,
  }) as Promise<MadeItemProcessResponse>
}
