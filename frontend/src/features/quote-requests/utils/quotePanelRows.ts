import type { QuoteRequestLineRequest } from '../types/quoteRequestsRequest'

/** The share of a panel row one demand is for. */
export interface QuotePanelShare {
  family: 'bought' | 'source'
  demandId: number
  quantity: number
}

/**
 * One row of the Manage Quotes panel, built by the table that hosts it: what
 * the line asks for (`identity`), how it is shown, its quantity, and the
 * demand shares it is for. `quantityEdited` is set once the user typed the
 * quantity; until then it follows the shares.
 */
export interface QuotePanelRow {
  key: string
  title: string
  subtitle: string
  projectNumber: string
  unit: string
  quantity: number
  quantityEdited: boolean
  maxQuantity?: number | null
  shares: QuotePanelShare[]
  identity: Pick<
    QuoteRequestLineRequest,
    'bought_item_id' | 'source_item_id' | 'lot_position_id' | 'project_id'
  >
}

const EPSILON = 1e-6

/**
 * The shares a row sends. A row of one demand shows no share, so that share
 * follows the line: it is cut to the line quantity when the user lowered it.
 */
function sentShares(row: QuotePanelRow): QuotePanelShare[] {
  const [only] = row.shares
  if (row.shares.length !== 1 || !only) return row.shares
  return [{ ...only, quantity: Math.min(only.quantity, row.quantity) }]
}

/** Whether the row shows its shares, which it does for more than one demand. */
export function rowShowsShares(row: QuotePanelRow): boolean {
  return row.shares.length > 1
}

export function rowSharesExceedLine(row: QuotePanelRow): boolean {
  const total = sentShares(row).reduce((sum, share) => sum + (share.quantity || 0), 0)
  return total > row.quantity + EPSILON
}

/** The request lines the rows add, without the shares of nothing. */
export function quotePanelLines(rows: QuotePanelRow[]): QuoteRequestLineRequest[] {
  return rows.map((row) => ({
    ...row.identity,
    quantity: row.quantity,
    unit: row.unit,
    demands: sentShares(row)
      .filter((share) => share.quantity > EPSILON)
      .map((share) => ({
        family: share.family,
        demand_item_id: share.demandId,
        quantity: share.quantity,
      })),
  }))
}

/**
 * The rows of a new selection, `fresh`, with what the user entered on the
 * `previous` rows kept: a row keeps an edited quantity and each demand
 * keeps its share; a row whose quantity was not typed follows its shares.
 */
export function mergeQuotePanelRows(
  previous: QuotePanelRow[],
  fresh: QuotePanelRow[],
): QuotePanelRow[] {
  const byKey = new Map(previous.map((row) => [row.key, row]))
  const shares = new Map(
    previous.flatMap((row) => row.shares.map((s) => [`${s.family}:${s.demandId}`, s.quantity] as const)),
  )
  return fresh.map((row) => {
    const kept = byKey.get(row.key)
    const merged: QuotePanelRow = {
      ...row,
      shares: row.shares.map((s) => ({
        ...s,
        quantity: shares.get(`${s.family}:${s.demandId}`) ?? s.quantity,
      })),
    }
    if (kept?.quantityEdited) {
      merged.quantity = kept.quantity
      merged.quantityEdited = true
    } else if (merged.shares.length > 0) {
      merged.quantity = merged.shares.reduce((sum, s) => sum + s.quantity, 0)
    }
    return merged
  })
}
