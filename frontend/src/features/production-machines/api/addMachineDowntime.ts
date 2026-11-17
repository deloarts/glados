import { webApi } from '@/core/api/webRequest'

import type {
  MachineDowntimeCreateRequest,
  MachineDowntimeResponse,
} from '../types/machineDowntimeResponse'

export async function addMachineDowntime(
  payload: MachineDowntimeCreateRequest,
): Promise<MachineDowntimeResponse> {
  return webApi.post('/production-machines/downtimes', {
    body: payload,
  })
}
