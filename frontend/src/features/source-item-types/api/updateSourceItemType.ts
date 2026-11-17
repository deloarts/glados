import { webApi } from '@/core/api/webRequest'

import type { SourceItemTypeUpdateRequest } from '../types/sourceItemTypeRequest'
import type { SourceItemTypeResponse } from '../types/sourceItemTypeResponse'

export async function updateSourceItemType(
  typeId: number,
  payload: SourceItemTypeUpdateRequest,
): Promise<SourceItemTypeResponse> {
  return webApi.put('/source-item-types/{source_item_type_id}', {
    path: { source_item_type_id: typeId },
    body: payload,
  })
}
