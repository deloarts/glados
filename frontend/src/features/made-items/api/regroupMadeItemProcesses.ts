import { webApi } from '@/core/api/webRequest'

import type { MadeItemProcessResponse } from '../types/madeItemsResponse'

export async function regroupMadeItemProcesses(
  itemId: number,
  groups: number[][],
): Promise<MadeItemProcessResponse[]> {
  // The processes are refined to the role union, see MadeItemProcessResponse.
  return webApi.put('/made-items/{item_id}/processes/regroup', {
    path: { item_id: itemId },
    body: { groups },
  }) as Promise<MadeItemProcessResponse[]>
}
