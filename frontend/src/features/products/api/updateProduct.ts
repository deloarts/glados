import { webApi } from '@/core/api/webRequest'

import type { ProductUpdateRequest } from '../types/productRequest'
import type { ProductResponse } from '../types/productResponse'

export async function updateProduct(
  productId: number,
  payload: ProductUpdateRequest,
): Promise<ProductResponse> {
  return webApi.put('/products/{product_id}', { path: { product_id: productId }, body: payload })
}
