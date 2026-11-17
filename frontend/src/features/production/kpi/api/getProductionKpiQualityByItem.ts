import { webApi } from '@/core/api/webRequest'

import type { ProductionKpiFilterParams } from '../types/productionKpiFilterParams'
import type { ProductionKpiQualityByItemResult } from '../types/productionKpiResponse'

export async function getProductionKpiQualityByItem(
  params: ProductionKpiFilterParams,
): Promise<ProductionKpiQualityByItemResult> {
  return webApi.get('/production-kpi/quality-by-item', { query: params })
}
