import { webApi } from '@/core/api/webRequest'
import type { ListPlaceTarget } from '@/shared/types/listOrder'

/** Puts the method next to another one, as dragging its row does. */
export async function placeInspectionMethod(methodId: number, target: ListPlaceTarget): Promise<void> {
  await webApi.post('/inspection-methods/{inspection_method_id}/place', {
    path: { inspection_method_id: methodId },
    body: target,
  })
}
