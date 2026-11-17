import { webApi } from '@/core/api/webRequest'
import type { Schemas } from '@/core/api/generated'

/** Costs, orders and demand counts summed over all projects of the product. */
export async function getProductSummary(productId: number): Promise<Schemas['ProjectSummaryResponse']> {
  return webApi.get('/products/{product_id}/summary', { path: { product_id: productId } })
}
