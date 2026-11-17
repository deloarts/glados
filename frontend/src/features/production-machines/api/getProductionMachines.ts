import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { ProductionMachineFilterParams } from '../types/productionMachinesRequest'
import type { ProductionMachineResponse } from '../types/productionMachinesResponse'

export async function getProductionMachines(
  params?: ProductionMachineFilterParams,
): Promise<PageResponse<ProductionMachineResponse>> {
  return webApi.get('/production-machines/', {
    query: params,
  })
}
