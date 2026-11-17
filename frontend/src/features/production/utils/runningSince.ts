import { parseBackendTimestamp } from '@/core/utils/dates'
import type { ProductionOrderResponse } from '../types/productionOrdersResponse'

/**
 * When a started order last began running: the later of its first start and
 * the end of its latest closed interruption, or null before the first start.
 * actual_start keeps the first start, so the schedule projections anchor a
 * resumed order here, at the same moment the backend scheduler uses. Labels
 * that say when an order started keep showing actual_start.
 */
export function runningSince(
  order: Pick<ProductionOrderResponse, 'actual_start' | 'interruptions'>,
): Date | null {
  if (!order.actual_start) return null
  let latest = parseBackendTimestamp(order.actual_start)
  for (const interruption of order.interruptions ?? []) {
    if (!interruption.resumed_at) continue
    const resumedAt = parseBackendTimestamp(interruption.resumed_at)
    if (resumedAt.getTime() > latest.getTime()) latest = resumedAt
  }
  return latest
}
