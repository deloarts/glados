import { webApi } from '@/core/api/webRequest'
import type { ListPlaceTarget } from '@/shared/types/listOrder'

/** Puts the group next to another one, as dragging its row does. */
export async function placeArticleGroup(groupId: number, target: ListPlaceTarget): Promise<void> {
  await webApi.post('/article-groups/{article_group_id}/place', {
    path: { article_group_id: groupId },
    body: target,
  })
}
