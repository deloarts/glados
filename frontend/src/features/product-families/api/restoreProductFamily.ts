import { webApi } from '@/core/api/webRequest'

import type { ProductFamilyResponse } from '../types/productFamilyResponse'

export async function restoreProductFamily(groupId: number): Promise<ProductFamilyResponse> {
  return webApi.post('/product-families/{product_family_id}/restore', {
    path: { product_family_id: groupId },
  })
}
