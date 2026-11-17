import { webApi } from '@/core/api/webRequest'

import type { MadeItemProcessUpdateRequest } from '../types/madeItemsRequest'
import type { MadeItemProcessResponse } from '../types/madeItemsResponse'

export async function updateMadeItemProcess(
  itemId: number,
  processId: number,
  payload: MadeItemProcessUpdateRequest,
): Promise<MadeItemProcessResponse> {
  // The process is refined to the role union, see MadeItemProcessResponse.
  return webApi.put('/made-items/{item_id}/processes/{process_id}', {
    path: { item_id: itemId, process_id: processId },
    body: payload,
  }) as Promise<MadeItemProcessResponse>
}
