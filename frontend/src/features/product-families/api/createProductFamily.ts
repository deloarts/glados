import { webApi } from '@/core/api/webRequest'

import type { ProductFamilyCreateRequest } from '../types/productFamilyRequest'
import type { ProductFamilyResponse } from '../types/productFamilyResponse'

export async function createProductFamily(
  payload: ProductFamilyCreateRequest,
): Promise<ProductFamilyResponse> {
  return webApi.post('/product-families/', { body: payload })
}
