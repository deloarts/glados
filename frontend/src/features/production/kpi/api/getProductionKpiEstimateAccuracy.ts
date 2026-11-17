import { webApi } from '@/core/api/webRequest'

import type { ProductionKpiFilterParams } from '../types/productionKpiFilterParams'
import type { ProductionKpiEstimateAccuracyResult } from '../types/productionKpiResponse'

export async function getProductionKpiEstimateAccuracy(
  params: ProductionKpiFilterParams,
): Promise<ProductionKpiEstimateAccuracyResult> {
  return webApi.get('/production-kpi/estimate-accuracy', { query: params })
}
