import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { ProductFamilyResponse } from '../types/productFamilyResponse'
import type { ProductFamilyFilterParams } from '../types/productFamilyRequest'

export async function getProductFamilies(
  params?: ProductFamilyFilterParams,
): Promise<PageResponse<ProductFamilyResponse>> {
  return webApi.get('/product-families/', { query: params })
}
