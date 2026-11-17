import { webApi } from '@/core/api/webRequest'
import type { PageResponse } from '@/core/api/types'
import type { CalculationListParams, CalculationSummaryResponse } from '../types/calculation'

export async function getCalculations(
  params: CalculationListParams,
): Promise<PageResponse<CalculationSummaryResponse>> {
  return webApi.get('/calculations', { query: params })
}
