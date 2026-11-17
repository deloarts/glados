import { webApi } from '@/core/api/webRequest'
import type { QueryOf } from '@/core/api/webRequest'

import type { TodoSourcesResponse } from '../types/todoSourcesResponse'

export async function getTodoSources(
  query: QueryOf<'/todo/sources'>,
): Promise<TodoSourcesResponse> {
  // The made demands and lots are refined to their role unions, see
  // TodoSourcesResponse.
  return webApi.get('/todo/sources', { query }) as Promise<TodoSourcesResponse>
}
