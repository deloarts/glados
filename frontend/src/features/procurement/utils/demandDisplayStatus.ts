import type { DemandSummaryResponse, BoughtItemDemandResponse } from '@/features/bought-items'

// The status a demand row shows. The stored status is the server's and
// drives server-side filtering; the live allocation summary only adds detail
// within it, e.g. stored "allocated" can show as "partially_ordered". A
// fulfilled or canceled demand always shows its stored status, since a
// manual fulfil leaves allocations that never arrive.
export type DemandDisplayStatus =
  | 'open'
  | 'partially_allocated'
  | 'allocated'
  | 'partially_ordered'
  | 'ordered'
  | 'partially_delivered'
  | 'fulfilled'
  | 'canceled'

const REFINEMENTS: Record<string, readonly DemandDisplayStatus[]> = {
  open: ['open'],
  allocated: ['partially_allocated', 'allocated', 'partially_ordered', 'partially_delivered'],
  ordered: ['ordered', 'partially_delivered'],
}

function fromSummary(summary: DemandSummaryResponse): DemandDisplayStatus {
  const { total, allocated, ordered, delivered, fulfilled_from_stock } = summary
  const covered = allocated + fulfilled_from_stock
  if (delivered + fulfilled_from_stock >= total) return 'fulfilled'
  if (delivered > 0) return 'partially_delivered'
  if (ordered >= total) return 'ordered'
  if (ordered > 0) return 'partially_ordered'
  if (covered >= total) return 'allocated'
  if (covered > 0) return 'partially_allocated'
  return 'open'
}

export function demandDisplayStatus(
  demand: Pick<BoughtItemDemandResponse, 'status'>,
  summary: DemandSummaryResponse | undefined,
): DemandDisplayStatus {
  const stored = demand.status as DemandDisplayStatus
  const refinements = REFINEMENTS[demand.status]
  if (!refinements || !summary) return stored
  const live = fromSummary(summary)
  return refinements.includes(live) ? live : stored
}
