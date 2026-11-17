import { webApi } from '@/core/api/webRequest'

import type {
  MachineCalendarExceptionResponse,
  MachineCalendarExceptionUpdateRequest,
} from '../types/machineCalendarResponse'

export async function updateMachineCalendarException(
  exceptionId: number,
  payload: MachineCalendarExceptionUpdateRequest,
): Promise<MachineCalendarExceptionResponse> {
  return webApi.patch('/production-machines/calendar-exceptions/{exception_id}', {
    path: { exception_id: exceptionId },
    body: payload,
  })
}
