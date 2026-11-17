import { webApi } from '@/core/api/webRequest'
import type { Schemas } from '@/core/api/generated'

export type ProductRenumberImpact = Schemas['ProductRenumberImpactResponse']

/** What changing the product's number to `newNumber` would affect. */
export function getRenumberImpact(
  productId: number,
  newNumber: string,
): Promise<ProductRenumberImpact> {
  return webApi.get('/products/{product_id}/renumber-impact', {
    path: { product_id: productId },
    query: { new_number: newNumber },
  })
}
