import { webApi } from '@/core/api/webRequest'

import type { ArticleGroupCreateRequest } from '../types/articleGroupRequest'
import type { ArticleGroupResponse } from '../types/articleGroupResponse'

export async function createArticleGroup(
  payload: ArticleGroupCreateRequest,
): Promise<ArticleGroupResponse> {
  return webApi.post('/article-groups/', { body: payload })
}
