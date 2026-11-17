import { webApi } from '@/core/api/webRequest'

import type { MadeItemUpdateRequest } from '../types/madeItemsRequest'
import type { MadeItemResponse } from '../types/madeItemsResponse'

export async function updateMadeItem(
  itemId: number,
  payload: MadeItemUpdateRequest,
): Promise<MadeItemResponse> {
  // processes are refined to the role union, see MadeItemProcessResponse.
  return webApi.put('/made-items/{item_id}', {
    path: { item_id: itemId },
    body: payload,
  }) as Promise<MadeItemResponse>
}
