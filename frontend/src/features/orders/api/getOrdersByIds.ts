import { getOrders } from './getOrders'

import type { OrderResponse } from '../types/ordersResponse'

// The backend accepts at most 200 ids per request.
const MAX_IDS_PER_REQUEST = 200

// Batches order lookups into GET /orders requests filtered by ids. limit is
// set to the chunk size, since the ids filter does not bypass pagination.
export async function getOrdersByIds(ids: number[]): Promise<OrderResponse[]> {
  const uniqueIds = [...new Set(ids)]
  if (uniqueIds.length === 0) return []

  const chunks: number[][] = []
  for (let i = 0; i < uniqueIds.length; i += MAX_IDS_PER_REQUEST) {
    chunks.push(uniqueIds.slice(i, i + MAX_IDS_PER_REQUEST))
  }

  const pages = await Promise.all(
    chunks.map((chunk) => getOrders({ ids: chunk, limit: chunk.length })),
  )
  return pages.flatMap((page) => page.items)
}
