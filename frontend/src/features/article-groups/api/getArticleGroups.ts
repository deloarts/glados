import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { ArticleGroupResponse } from '../types/articleGroupResponse'
import type { ArticleGroupFilterParams } from '../types/articleGroupRequest'

export async function getArticleGroups(
  params?: ArticleGroupFilterParams,
): Promise<PageResponse<ArticleGroupResponse>> {
  return webApi.get('/article-groups/', { query: params })
}
