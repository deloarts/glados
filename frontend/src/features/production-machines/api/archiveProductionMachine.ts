import { webApi } from '@/core/api/webRequest'

import type { ProductionMachineResponse } from '../types/productionMachinesResponse'

export async function archiveProductionMachine(
  machineId: number,
): Promise<ProductionMachineResponse> {
  return webApi.post('/production-machines/{machine_id}/archive', {
    path: { machine_id: machineId },
  })
}
