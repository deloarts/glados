import { webApi } from '@/core/api/webRequest'

import type { ProductionKpiFilterParams } from '../types/productionKpiFilterParams'
import type { ProductionKpiWeeklyResult } from '../types/productionKpiResponse'

export async function getProductionKpiWeekly(
  params: ProductionKpiFilterParams,
): Promise<ProductionKpiWeeklyResult> {
  return webApi.get('/production-kpi/weekly', { query: params })
}
