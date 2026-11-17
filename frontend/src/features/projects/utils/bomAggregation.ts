/**
 * Rolls demand items up into one row per item, or per item and project when
 * the bill spans several projects. The three bills of material share the
 * fold and inject their accessors.
 */

export interface BomRowBase {
  /**
   * A string key, since a source item demand points at a bought or a source
   * item and the id spaces overlap.
   */
  key: string
  qtyDemanded: number
  qtyFulfilled: number
  statusCounts: Record<string, number>
  /** Set when the bill splits its rows by project. */
  projectNumber?: string
}

type BomRowSeed<TRow extends BomRowBase> = Omit<
  TRow,
  'qtyDemanded' | 'qtyFulfilled' | 'statusCounts'
>

export function aggregateBomRows<TDemand, TRow extends BomRowBase>(
  demands: TDemand[],
  opts: {
    key: (demand: TDemand) => string
    /**
     * Builds the row's non-accumulating fields from the first demand seen
     * for that key. Later demands for the same item only add quantities.
     */
    seed: (demand: TDemand, key: string) => BomRowSeed<TRow>
    quantity: (demand: TDemand) => number
    status: (demand: TDemand) => string
    compare: (a: TRow, b: TRow) => number
    /** Splits an item's row by the project of its demands. */
    project?: (demand: TDemand) => { id: number; number: string }
  },
): TRow[] {
  const map = new Map<string, TRow>()

  for (const demand of demands) {
    const project = opts.project?.(demand)
    const key = project ? `${project.id}:${opts.key(demand)}` : opts.key(demand)
    let row = map.get(key)
    if (!row) {
      row = {
        ...opts.seed(demand, key),
        qtyDemanded: 0,
        qtyFulfilled: 0,
        statusCounts: {},
      } as TRow
      if (project) row.projectNumber = project.number
      map.set(key, row)
    }

    const status = opts.status(demand)
    row.qtyDemanded += opts.quantity(demand)
    if (status === 'fulfilled') row.qtyFulfilled += opts.quantity(demand)
    row.statusCounts[status] = (row.statusCounts[status] ?? 0) + 1
  }

  // An item's rows of several projects stay together, in project order.
  return [...map.values()].sort(
    (a, b) => opts.compare(a, b) || (a.projectNumber ?? '').localeCompare(b.projectNumber ?? ''),
  )
}

/**
 * Sorts by one field with a tiebreak, keeping rows of a rowspan group in a
 * stable order.
 */
export function compareBy<TRow>(
  primary: (row: TRow) => string,
  secondary: (row: TRow) => string,
): (a: TRow, b: TRow) => number {
  return (a, b) => {
    const result = primary(a).localeCompare(primary(b))
    return result !== 0 ? result : secondary(a).localeCompare(secondary(b))
  }
}
