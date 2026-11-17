import { webApi } from '@/core/api/webRequest'

import type {
  MachineCalendarExceptionCreateRequest,
  MachineCalendarExceptionResponse,
} from '../types/machineCalendarResponse'

export async function createMachineCalendarException(
  machineId: number,
  payload: MachineCalendarExceptionCreateRequest,
): Promise<MachineCalendarExceptionResponse> {
  return webApi.post('/production-machines/{machine_id}/calendar-exceptions', {
    path: { machine_id: machineId },
    body: payload,
  })
}
