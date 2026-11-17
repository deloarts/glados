import { webApi } from '@/core/api/webRequest'
import type { ProductVariant, ProductVariantRequest } from '../types/sequence'

export function getProductVariants(productId: number, includeArchived = false): Promise<ProductVariant[]> {
  return webApi.get('/products/{product_id}/variants', {
    path: { product_id: productId },
    query: { include_archived: includeArchived },
  })
}

/** Saves the whole list in its order; a variant left out is archived. */
export function saveProductVariants(productId: number, variants: ProductVariantRequest[]): Promise<ProductVariant[]> {
  return webApi.put('/products/{product_id}/variants', { path: { product_id: productId }, body: { variants } })
}
