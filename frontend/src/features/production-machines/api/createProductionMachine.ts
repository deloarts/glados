import { webApi } from '@/core/api/webRequest'

import type { ProductionMachineCreateRequest } from '../types/productionMachinesRequest'
import type { ProductionMachineResponse } from '../types/productionMachinesResponse'

export async function createProductionMachine(
  payload: ProductionMachineCreateRequest,
): Promise<ProductionMachineResponse> {
  return webApi.post('/production-machines/', {
    body: payload,
  })
}
