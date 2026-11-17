import { webApi } from '@/core/api/webRequest'

import type { ProductionKpiFilterParams } from '../types/productionKpiFilterParams'
import type { ProductionKpiScrapByReasonResult } from '../types/productionKpiResponse'

export async function getProductionKpiScrapByReason(
  params: ProductionKpiFilterParams,
): Promise<ProductionKpiScrapByReasonResult> {
  return webApi.get('/production-kpi/scrap-by-reason', { query: params })
}
