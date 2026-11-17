import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { SourceItemTypeResponse } from '../types/sourceItemTypeResponse'
import type { SourceItemTypeFilterParams } from '../types/sourceItemTypeRequest'

export async function getSourceItemTypes(
  params?: SourceItemTypeFilterParams,
): Promise<PageResponse<SourceItemTypeResponse>> {
  return webApi.get('/source-item-types/', { query: params })
}
