import { webApi } from '@/core/api/webRequest'

import type { MadeItemCreateRevisionRequest } from '../types/madeItemsRequest'
import type { MadeItemResponse } from '../types/madeItemsResponse'

/**
 * `POST /made-items/{id}/revisions`: full copy of `payload.item` onto a
 * new row sharing `itemId`'s part number, revision incremented server-side;
 * `itemId`'s own row becomes `payload.predecessor_status`. Requires
 * `write:made_items`.
 */
export async function createMadeItemRevision(
  itemId: number,
  payload: MadeItemCreateRevisionRequest,
): Promise<MadeItemResponse> {
  // processes are refined to the role union, see MadeItemProcessResponse.
  return webApi.post('/made-items/{item_id}/revisions', {
    path: { item_id: itemId },
    body: payload,
  }) as Promise<MadeItemResponse>
}
