import { webApi } from '@/core/api/webRequest'

import type { SourceItemTypeCreateRequest } from '../types/sourceItemTypeRequest'
import type { SourceItemTypeResponse } from '../types/sourceItemTypeResponse'

export async function createSourceItemType(
  payload: SourceItemTypeCreateRequest,
): Promise<SourceItemTypeResponse> {
  return webApi.post('/source-item-types/', { body: payload })
}
