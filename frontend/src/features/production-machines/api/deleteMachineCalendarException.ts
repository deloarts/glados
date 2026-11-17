import { webApi } from '@/core/api/webRequest'

export async function deleteMachineCalendarException(exceptionId: number): Promise<void> {
  await webApi.delete('/production-machines/calendar-exceptions/{exception_id}', {
    path: { exception_id: exceptionId },
  })
}
