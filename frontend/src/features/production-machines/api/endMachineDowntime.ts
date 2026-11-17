import { webApi } from '@/core/api/webRequest'

import type {
  MachineDowntimeEndRequest,
  MachineDowntimeResponse,
} from '../types/machineDowntimeResponse'

export async function endMachineDowntime(
  downtimeId: number,
  payload: MachineDowntimeEndRequest = {},
): Promise<MachineDowntimeResponse> {
  return webApi.post('/production-machines/downtimes/{downtime_id}/end', {
    path: { downtime_id: downtimeId },
    body: payload,
  })
}
