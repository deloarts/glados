import { webApi } from '@/core/api/webRequest'

import type { MachinePoolResponse } from '../types/machinePoolsResponse'

export async function archiveMachinePool(poolId: number): Promise<MachinePoolResponse> {
  return webApi.post('/production-machine-pools/{pool_id}/archive', {
    path: { pool_id: poolId },
  })
}
