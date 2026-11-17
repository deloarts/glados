import { webApi } from '@/core/api/webRequest'

import type { ProductionKpiFilterParams } from '../types/productionKpiFilterParams'
import type { ProductionKpiLateLotsResult } from '../types/productionKpiResponse'

// The backend ignores date_from/date_to for this endpoint (lateness is
// evaluated against a lot's current state, not a period aggregate), but the
// query schema still requires them like every other production-kpi
// endpoint, so the store passes the active period's dates along regardless.
export async function getProductionKpiLateLots(
  params: ProductionKpiFilterParams,
): Promise<ProductionKpiLateLotsResult> {
  return webApi.get('/production-kpi/late-lots', { query: params })
}
