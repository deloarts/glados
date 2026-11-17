import type { Schemas } from '@/core/api/generated'
import { webApi } from '@/core/api/webRequest'

/** The product of a sequence, for the rights on its devices and its disciplines. */
export type SequenceProduct = Schemas['ProductWebResponse']

export function getSequenceProduct(productId: number): Promise<SequenceProduct> {
  return webApi.get('/products/{product_id}', { path: { product_id: productId } })
}
