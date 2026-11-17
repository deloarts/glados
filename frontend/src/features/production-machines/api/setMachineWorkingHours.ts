import { webApi } from '@/core/api/webRequest'

import type {
  MachineWorkingHoursResponse,
  MachineWorkingHoursSetRequest,
} from '../types/machineCalendarResponse'

export async function setMachineWorkingHours(
  machineId: number,
  payload: MachineWorkingHoursSetRequest,
): Promise<MachineWorkingHoursResponse> {
  return webApi.put('/production-machines/{machine_id}/working-hours', {
    path: { machine_id: machineId },
    body: payload,
  })
}
