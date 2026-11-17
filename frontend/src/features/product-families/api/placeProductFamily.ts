import { webApi } from '@/core/api/webRequest'
import type { ListPlaceTarget } from '@/shared/types/listOrder'

/** Puts the family next to another one, as dragging its row does. */
export async function placeProductFamily(familyId: number, target: ListPlaceTarget): Promise<void> {
  await webApi.post('/product-families/{product_family_id}/place', {
    path: { product_family_id: familyId },
    body: target,
  })
}
