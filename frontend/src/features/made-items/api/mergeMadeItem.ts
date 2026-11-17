import { webApi } from '@/core/api/webRequest'

import type { MadeItemResponse } from '../types/madeItemsResponse'

export async function mergeMadeItem(sourceId: number, targetId: number): Promise<MadeItemResponse> {
  // processes are refined to the role union, see MadeItemProcessResponse.
  return webApi.post('/made-items/{item_id}/merge', {
    path: { item_id: sourceId },
    body: {
      target_id: targetId,
    },
  }) as Promise<MadeItemResponse>
}
