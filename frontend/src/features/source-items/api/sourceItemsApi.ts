import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type {
  SourceItemCreateRequest,
  SourceItemFilterParams,
  SourceItemUpdateRequest,
} from '../types/sourceItemsRequest'
import type { SourceItemResponse } from '../types/sourceItemsResponse'

/**
 * The source-item catalogue's own routes. A source item is archived and
 * restored rather than deleted.
 */
export const sourceItemsApi = {
  async list(params?: SourceItemFilterParams): Promise<PageResponse<SourceItemResponse>> {
    return webApi.get('/source-items', { query: params })
  },

  async create(body: SourceItemCreateRequest): Promise<SourceItemResponse> {
    return webApi.post('/source-items', { body })
  },

  async update(id: number, body: SourceItemUpdateRequest): Promise<SourceItemResponse> {
    return webApi.put('/source-items/{item_id}', { path: { item_id: id }, body })
  },

  async archive(id: number): Promise<SourceItemResponse> {
    return webApi.post('/source-items/{item_id}/archive', { path: { item_id: id } })
  },

  async restore(id: number): Promise<SourceItemResponse> {
    return webApi.post('/source-items/{item_id}/restore', { path: { item_id: id } })
  },
}
