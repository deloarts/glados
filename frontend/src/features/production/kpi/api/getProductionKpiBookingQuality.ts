import { webApi } from '@/core/api/webRequest'

import type { ProductionKpiFilterParams } from '../types/productionKpiFilterParams'
import type { ProductionKpiBookingQualityResult } from '../types/productionKpiResponse'

export async function getProductionKpiBookingQuality(
  params: ProductionKpiFilterParams,
): Promise<ProductionKpiBookingQualityResult> {
  return webApi.get('/production-kpi/booking-quality', { query: params })
}
