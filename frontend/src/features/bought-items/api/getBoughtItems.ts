import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { WebRequestConfig } from '@/core/api/webRequest'
import type { BoughtItemFilterParams } from '../types/boughtItemsRequest'
import type { BoughtItemResponse } from '../types/boughtItemsResponse'

export async function getBoughtItems(
  params?: BoughtItemFilterParams,
  config?: WebRequestConfig,
): Promise<PageResponse<BoughtItemResponse>> {
  return webApi.get('/bought-items/', { query: params, config })
}
