import { webApi } from '@/core/api/webRequest'

import type { ProductResponse } from '../types/productResponse'

export async function archiveProduct(productId: number): Promise<ProductResponse> {
  return webApi.post('/products/{product_id}/archive', { path: { product_id: productId } })
}
