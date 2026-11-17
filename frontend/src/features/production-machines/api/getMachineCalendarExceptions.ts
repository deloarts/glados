import { webApi } from '@/core/api/webRequest'

import type { MachineCalendarExceptionResponse } from '../types/machineCalendarResponse'

export async function getMachineCalendarExceptions(
  machineId: number,
): Promise<MachineCalendarExceptionResponse[]> {
  return webApi.get('/production-machines/{machine_id}/calendar-exceptions', {
    path: { machine_id: machineId },
  })
}
