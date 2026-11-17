import { webApi } from '@/core/api/webRequest'

import type { ProductionMachineUpdateRequest } from '../types/productionMachinesRequest'
import type { ProductionMachineResponse } from '../types/productionMachinesResponse'

export async function updateProductionMachine(
  machineId: number,
  payload: ProductionMachineUpdateRequest,
): Promise<ProductionMachineResponse> {
  // Backend exposes this as PATCH (partial update), not PUT.
  return webApi.patch('/production-machines/{machine_id}', {
    path: { machine_id: machineId },
    body: payload,
  })
}
