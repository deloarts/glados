import { webApi } from '@/core/api/webRequest'

import type { GlobalSearchResponse } from '../types/globalSearchResponse'

export async function globalSearch(q: string, limit = 5): Promise<GlobalSearchResponse> {
  return webApi.get('/search/', { query: { q, limit } })
}
