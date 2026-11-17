import { webApi } from '@/core/api/webRequest'

import type { SourceItemTypeResponse } from '../types/sourceItemTypeResponse'

export async function restoreSourceItemType(typeId: number): Promise<SourceItemTypeResponse> {
  return webApi.post('/source-item-types/{source_item_type_id}/restore', {
    path: { source_item_type_id: typeId },
  })
}
