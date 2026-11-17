import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { WebRequestConfig } from '@/core/api/webRequest'
import type { MadeItemFilterParams } from '../types/madeItemsRequest'
import type { MadeItemResponse } from '../types/madeItemsResponse'

export async function getMadeItems(
  params?: MadeItemFilterParams,
  config?: WebRequestConfig,
): Promise<PageResponse<MadeItemResponse>> {
  // processes are refined to the role union, see MadeItemProcessResponse.
  return webApi.get('/made-items/', { query: params, config }) as Promise<PageResponse<MadeItemResponse>>
}
