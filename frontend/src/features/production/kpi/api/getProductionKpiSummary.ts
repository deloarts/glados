import { webApi } from '@/core/api/webRequest'

import type { ProductionKpiFilterParams } from '../types/productionKpiFilterParams'
import type { ProductionKpiSummaryResult } from '../types/productionKpiResponse'

export async function getProductionKpiSummary(
  params: ProductionKpiFilterParams,
): Promise<ProductionKpiSummaryResult> {
  return webApi.get('/production-kpi/summary', { query: params })
}
