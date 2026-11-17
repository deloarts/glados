import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { QaTaskFilterParams, QaTaskResponse } from '../types/qaTaskResponse'

export async function getQaTasks(
  params?: QaTaskFilterParams,
): Promise<PageResponse<QaTaskResponse>> {
  return webApi.get('/production-qa/', { query: params })
}
