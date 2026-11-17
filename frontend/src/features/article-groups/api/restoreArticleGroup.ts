import { webApi } from '@/core/api/webRequest'

import type { ArticleGroupResponse } from '../types/articleGroupResponse'

export async function restoreArticleGroup(groupId: number): Promise<ArticleGroupResponse> {
  return webApi.post('/article-groups/{article_group_id}/restore', {
    path: { article_group_id: groupId },
  })
}
