import type { LocalizedText } from '@/shared/utils/localizedText'
import type {
  ExternalWorkGroupBy,
  ExternalWorkRow,
  ExternalWorkStage,
} from '../types/externalWork'

/**
 * Where a position stands with its supplier. Pieces already handed over
 * put it at the supplier, whatever the line says, until some come back.
 */
export function externalWorkStage(row: ExternalWorkRow): ExternalWorkStage {
  if (row.order_item_id === null) return 'unassigned'
  if (row.order_item_status === 'partially_delivered') return 'partially_back'
  if (row.handed_over_quantity > 0) return 'at_supplier'
  if (row.order_item_status === 'pending') return 'pending'
  if (row.order_item_status === 'requested') return 'requested'
  return 'ordered'
}

/** The supplier a row belongs to: its line's, else the method's suggestion. */
export function externalWorkSupplier(row: ExternalWorkRow): string {
  return row.order_item_id !== null ? row.supplier_name : row.suggested_supplier_name
}

/** The group a row sits in, as a label; empty for a row without one. */
export function externalWorkGroupLabel(
  row: ExternalWorkRow,
  groupBy: ExternalWorkGroupBy,
  localize: (text: LocalizedText) => string,
): string {
  if (groupBy === 'supplier') return externalWorkSupplier(row)
  return row.fabrication_methods.map((method) => localize(method.name)).join(', ')
}

/** Whether a row needs attention: it cannot be ready in time or is overdue. */
export function isCriticalExternalWork(row: ExternalWorkRow): boolean {
  return row.alert === 'not_ready_in_time' || row.alert === 'overdue'
}

export interface ExternalWorkGroupSummary {
  count: number
  critical: number
  // The earliest latest pickup among the rows nothing was handed over for.
  nextLatestPickup: string | null
}

/** What a group header says about the rows of one group. */
export function summarizeExternalWorkGroup(rows: ExternalWorkRow[]): ExternalWorkGroupSummary {
  const open = rows
    .filter((row) => row.handed_over_quantity <= 0 && row.latest_pickup_date !== null)
    .map((row) => row.latest_pickup_date as string)
    .sort()
  return {
    count: rows.length,
    critical: rows.filter(isCriticalExternalWork).length,
    nextLatestPickup: open[0] ?? null,
  }
}
