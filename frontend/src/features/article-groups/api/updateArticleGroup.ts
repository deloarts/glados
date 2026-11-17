import { webApi } from '@/core/api/webRequest'

import type { ArticleGroupUpdateRequest } from '../types/articleGroupRequest'
import type { ArticleGroupResponse } from '../types/articleGroupResponse'

export async function updateArticleGroup(
  groupId: number,
  payload: ArticleGroupUpdateRequest,
): Promise<ArticleGroupResponse> {
  return webApi.put('/article-groups/{article_group_id}', {
    path: { article_group_id: groupId },
    body: payload,
  })
}
