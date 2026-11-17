import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { ProductFilterParams } from '../types/productRequest'
import type { ProductResponse } from '../types/productResponse'

export async function getProducts(
  params?: ProductFilterParams,
): Promise<PageResponse<ProductResponse>> {
  return webApi.get('/products/', { query: params })
}
