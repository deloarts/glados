import { webApi } from '@/core/api/webRequest'

import type { BoughtItemMergeTargetResponse } from '../types/boughtItemsResponse'

/**
 * The items the catalogue search finds for `search`, each with whether it
 * may take the merge of item `sourceId` and why not.
 */
export async function getBoughtItemMergeTargets(
  sourceId: number,
  search: string,
): Promise<BoughtItemMergeTargetResponse[]> {
  return webApi.get('/bought-items/{item_id}/merge-targets', {
    path: { item_id: sourceId },
    query: search ? { search } : {},
  })
}
