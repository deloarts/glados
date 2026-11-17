import { getLots } from '../../api/getLots'

import type { LotSummaryResponse } from '../../types/productionLotsResponse'

// Batches N would-be `GET /production-lots/{id}` lookups into a single
// `GET /production-lots` request filtered by ids, mirroring the pattern
// used by getMadeItemDemandSummaryBatch for allocation summaries. The
// endpoint already supports this; ProductionLotsListView's live-rows
// refetch uses the same `{ ids }` filter.
export async function getLotsByIds(ids: number[]): Promise<LotSummaryResponse[]> {
  if (ids.length === 0) return []

  const response = await getLots({ ids, limit: ids.length })
  return response.items
}
