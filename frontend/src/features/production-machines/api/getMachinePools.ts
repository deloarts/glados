import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { MachinePoolFilterParams, MachinePoolResponse } from '../types/machinePoolsResponse'

export async function getMachinePools(
  params?: MachinePoolFilterParams,
): Promise<PageResponse<MachinePoolResponse>> {
  return webApi.get('/production-machine-pools/', {
    query: params,
  })
}
