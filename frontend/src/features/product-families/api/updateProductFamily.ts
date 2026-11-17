import { webApi } from '@/core/api/webRequest'

import type { ProductFamilyUpdateRequest } from '../types/productFamilyRequest'
import type { ProductFamilyResponse } from '../types/productFamilyResponse'

export async function updateProductFamily(
  groupId: number,
  payload: ProductFamilyUpdateRequest,
): Promise<ProductFamilyResponse> {
  return webApi.put('/product-families/{product_family_id}', {
    path: { product_family_id: groupId },
    body: payload,
  })
}
