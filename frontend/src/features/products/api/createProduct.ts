import { webApi } from '@/core/api/webRequest'

import type { ProductCreateRequest } from '../types/productRequest'
import type { ProductResponse } from '../types/productResponse'

export async function createProduct(payload: ProductCreateRequest): Promise<ProductResponse> {
  return webApi.post('/products/', { body: payload })
}
