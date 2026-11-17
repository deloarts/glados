import { webApi } from '@/core/api/webRequest'

import type { ProductionKpiFilterParams } from '../types/productionKpiFilterParams'
import type { ProductionKpiUtilizationResult } from '../types/productionKpiResponse'

export async function getProductionKpiUtilization(
  params: ProductionKpiFilterParams,
): Promise<ProductionKpiUtilizationResult> {
  return webApi.get('/production-kpi/utilization', { query: params })
}
