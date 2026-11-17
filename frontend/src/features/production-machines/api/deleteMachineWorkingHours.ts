import { webApi } from '@/core/api/webRequest'

// Removes the machine's override; it reverts to the global default calendar.
export async function deleteMachineWorkingHours(machineId: number): Promise<void> {
  await webApi.delete('/production-machines/{machine_id}/working-hours', {
    path: { machine_id: machineId },
  })
}
