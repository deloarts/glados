import { webApi } from '@/core/api/webRequest'

import type { MadeItemResponse } from '../types/madeItemsResponse'

export async function archiveMadeItem(itemId: number): Promise<MadeItemResponse> {
  // processes are refined to the role union, see MadeItemProcessResponse.
  return webApi.post('/made-items/{item_id}/archive', {
    path: { item_id: itemId },
  }) as Promise<MadeItemResponse>
}
