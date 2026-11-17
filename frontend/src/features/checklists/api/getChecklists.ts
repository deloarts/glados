import { webApi } from '@/core/api/webRequest'
import type { PageResponse } from '@/core/api/types'
import type { ChecklistListParams, ChecklistSummaryResponse } from '../types/checklist'

export async function getChecklists(
  params: ChecklistListParams,
): Promise<PageResponse<ChecklistSummaryResponse>> {
  return webApi.get('/checklists', { query: params })
}
