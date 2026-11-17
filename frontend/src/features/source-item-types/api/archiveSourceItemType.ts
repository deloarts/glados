import { webApi } from '@/core/api/webRequest'

import type { SourceItemTypeResponse } from '../types/sourceItemTypeResponse'

export async function archiveSourceItemType(typeId: number): Promise<SourceItemTypeResponse> {
  return webApi.post('/source-item-types/{source_item_type_id}/archive', {
    path: { source_item_type_id: typeId },
  })
}
