import { webApi } from '@/core/api/webRequest'

import type { ProductionMachineResponse } from '../types/productionMachinesResponse'

export async function restoreProductionMachine(
  machineId: number,
): Promise<ProductionMachineResponse> {
  return webApi.post('/production-machines/{machine_id}/restore', {
    path: { machine_id: machineId },
  })
}
