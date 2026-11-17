import { webApi } from '@/core/api/webRequest'

import type { MachinePoolResponse, MachinePoolUpdateRequest } from '../types/machinePoolsResponse'

export async function updateMachinePool(
  poolId: number,
  payload: MachinePoolUpdateRequest,
): Promise<MachinePoolResponse> {
  // Backend exposes this as PATCH (partial update), mirroring updateProductionMachine.
  return webApi.patch('/production-machine-pools/{pool_id}', {
    path: { pool_id: poolId },
    body: payload,
  })
}
