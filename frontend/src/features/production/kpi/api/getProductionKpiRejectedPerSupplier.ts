import { webApi } from '@/core/api/webRequest'

import type { ProductionKpiFilterParams } from '../types/productionKpiFilterParams'
import type { ProductionKpiRejectedPerSupplierResult } from '../types/productionKpiResponse'

export async function getProductionKpiRejectedPerSupplier(
  params: ProductionKpiFilterParams,
): Promise<ProductionKpiRejectedPerSupplierResult> {
  return webApi.get('/production-kpi/rejected-per-supplier', { query: params })
}
