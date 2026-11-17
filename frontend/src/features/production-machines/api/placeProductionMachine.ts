import { webApi } from '@/core/api/webRequest'
import type { ListPlaceTarget } from '@/shared/types/listOrder'

/** Puts the machine next to another one, as dragging its row does. */
export async function placeProductionMachine(machineId: number, target: ListPlaceTarget): Promise<void> {
  await webApi.post('/production-machines/{machine_id}/place', {
    path: { machine_id: machineId },
    body: target,
  })
}
