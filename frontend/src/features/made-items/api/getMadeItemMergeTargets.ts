import { webApi } from '@/core/api/webRequest'

import type { MadeItemMergeTargetResponse } from '../types/madeItemsResponse'

/**
 * The items the catalogue search finds for `search`, each with whether it
 * may take the merge of item `sourceId` and why not.
 */
export async function getMadeItemMergeTargets(
  sourceId: number,
  search: string,
): Promise<MadeItemMergeTargetResponse[]> {
  // processes are refined to the role union, see MadeItemProcessResponse.
  return webApi.get('/made-items/{item_id}/merge-targets', {
    path: { item_id: sourceId },
    query: search ? { search } : {},
  }) as Promise<MadeItemMergeTargetResponse[]>
}
