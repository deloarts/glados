import { webApi } from '@/core/api/webRequest'
import type { ListPlaceTarget } from '@/shared/types/listOrder'

/** Puts the method next to another one, as dragging its row does. */
export async function placeFabricationMethod(methodId: number, target: ListPlaceTarget): Promise<void> {
  await webApi.post('/fabrication-methods/{fabrication_method_id}/place', {
    path: { fabrication_method_id: methodId },
    body: target,
  })
}
