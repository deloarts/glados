import { webApi } from '@/core/api/webRequest'

import type { MachineWorkingHoursResponse } from '../types/machineCalendarResponse'

// null means the machine has no override and uses the global default calendar.
export async function getMachineWorkingHours(
  machineId: number,
): Promise<MachineWorkingHoursResponse | null> {
  return webApi.get('/production-machines/{machine_id}/working-hours', {
    path: { machine_id: machineId },
  })
}
