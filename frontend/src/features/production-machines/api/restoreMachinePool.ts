import { webApi } from '@/core/api/webRequest'

import type { MachinePoolResponse } from '../types/machinePoolsResponse'

export async function restoreMachinePool(poolId: number): Promise<MachinePoolResponse> {
  return webApi.post('/production-machine-pools/{pool_id}/restore', {
    path: { pool_id: poolId },
  })
}
