import { webApi } from '@/core/api/webRequest'

import type { MachinePoolCreateRequest, MachinePoolResponse } from '../types/machinePoolsResponse'

export async function createMachinePool(
  payload: MachinePoolCreateRequest,
): Promise<MachinePoolResponse> {
  return webApi.post('/production-machine-pools/', {
    body: payload,
  })
}
