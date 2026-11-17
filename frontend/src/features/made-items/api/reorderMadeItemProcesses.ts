import { webApi } from '@/core/api/webRequest'

import type { MadeItemProcessResponse } from '../types/madeItemsResponse'

export async function reorderMadeItemProcesses(
  itemId: number,
  orderedProcessIds: number[],
): Promise<MadeItemProcessResponse[]> {
  // The processes are refined to the role union, see MadeItemProcessResponse.
  return webApi.put('/made-items/{item_id}/processes/reorder', {
    path: { item_id: itemId },
    body: { ordered_process_ids: orderedProcessIds },
  }) as Promise<MadeItemProcessResponse[]>
}
