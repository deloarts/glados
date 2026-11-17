import { webApi } from '@/core/api/webRequest'

import type { ProductionKpiFilterParams } from '../types/productionKpiFilterParams'
import type { ProductionKpiWaitingTimeResult } from '../types/productionKpiResponse'

export async function getProductionKpiWaitingTime(
  params: ProductionKpiFilterParams,
): Promise<ProductionKpiWaitingTimeResult> {
  return webApi.get('/production-kpi/waiting-time', { query: params })
}
