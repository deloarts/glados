import { webApi } from '@/core/api/webRequest'

import type { ProductResponse } from '../types/productResponse'

export async function restoreProduct(productId: number): Promise<ProductResponse> {
  return webApi.post('/products/{product_id}/restore', { path: { product_id: productId } })
}
