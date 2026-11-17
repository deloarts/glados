import { webApi } from '@/core/api/webRequest'
import type { ListPlaceTarget } from '@/shared/types/listOrder'

/** Puts the type next to another one, as dragging its row does. */
export async function placeSourceItemType(typeId: number, target: ListPlaceTarget): Promise<void> {
  await webApi.post('/source-item-types/{source_item_type_id}/place', {
    path: { source_item_type_id: typeId },
    body: target,
  })
}
