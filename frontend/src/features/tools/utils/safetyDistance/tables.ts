/**
 * Numeric tables of ISO 13855:2024 and their lookups. The standard forbids
 * interpolation, so a value between two grid points is always read on the
 * side that gives the larger reach distance. The grid lookup also serves the
 * reach-over tables of ISO 13857:2019.
 */

/** Columns of Table 2: effective top edge H_DT of the detection zone. */
export const REACH_OVER_TOP_EDGES = [900, 1000, 1100, 1200, 1300, 1400, 1600, 1800, 2000, 2200, 2400, 2600] as const

export interface ReachOverRow {
  hazardHeight: number
  values: readonly number[]
}

/** Table 2: reach distance D_DO over a vertical detection zone, rows by hazard height H_H. */
export const REACH_OVER: readonly ReachOverRow[] = [
  { hazardHeight: 2600, values: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
  { hazardHeight: 2500, values: [400, 400, 350, 300, 300, 300, 300, 300, 250, 150, 100, 0] },
  { hazardHeight: 2400, values: [550, 550, 550, 500, 450, 450, 400, 400, 300, 250, 100, 0] },
  { hazardHeight: 2200, values: [800, 750, 750, 700, 650, 650, 600, 550, 400, 250, 0, 0] },
  { hazardHeight: 2000, values: [950, 950, 850, 850, 800, 750, 700, 550, 400, 0, 0, 0] },
  { hazardHeight: 1800, values: [1100, 1100, 950, 950, 850, 800, 750, 550, 0, 0, 0, 0] },
  { hazardHeight: 1600, values: [1150, 1150, 1100, 1000, 900, 850, 750, 450, 0, 0, 0, 0] },
  { hazardHeight: 1400, values: [1200, 1200, 1100, 1000, 900, 850, 650, 0, 0, 0, 0, 0] },
  { hazardHeight: 1200, values: [1200, 1200, 1100, 1000, 850, 800, 0, 0, 0, 0, 0, 0] },
  { hazardHeight: 1000, values: [1200, 1150, 1050, 950, 750, 700, 0, 0, 0, 0, 0, 0] },
  { hazardHeight: 800, values: [1150, 1050, 950, 800, 500, 450, 0, 0, 0, 0, 0, 0] },
  { hazardHeight: 600, values: [1050, 950, 750, 550, 0, 0, 0, 0, 0, 0, 0, 0] },
  { hazardHeight: 400, values: [900, 700, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
  { hazardHeight: 200, values: [600, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
  { hazardHeight: 0, values: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
]

export interface HeightRow {
  hazardHeight: number
  reach: number
}

/** Table 3: reach distance D_DU under a vertical detection zone when d_e + H_DB exceeds 40 mm. */
export const REACH_UNDER: readonly HeightRow[] = [
  { hazardHeight: 0, reach: 850 },
  { hazardHeight: 300, reach: 850 },
  { hazardHeight: 500, reach: 800 },
  { hazardHeight: 700, reach: 700 },
  { hazardHeight: 900, reach: 450 },
  { hazardHeight: 1100, reach: 0 },
]

/** Table 4: reach distance D_GU under a protective structure with 120 < H_GB ≤ 180 mm. */
export const REACH_UNDER_STRUCTURE: readonly HeightRow[] = [
  { hazardHeight: 0, reach: 900 },
  { hazardHeight: 200, reach: 900 },
  { hazardHeight: 400, reach: 900 },
  { hazardHeight: 600, reach: 900 },
  { hazardHeight: 800, reach: 800 },
  { hazardHeight: 1000, reach: 600 },
  { hazardHeight: 1200, reach: 0 },
]

/** Rows and columns of Table 5, the gap b = G_W · sin ω of a hinged guard. */
export const HINGE_GUARD_WIDTHS = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500] as const
export const HINGE_ANGLES = [3, 4, 5, 6, 7, 8, 9] as const

/** Gap b between frame and guard leaf when a cam operated switch trips (12.2.2, equation 39). */
export function hingeGap(guardWidth: number, angleDeg: number): number {
  return guardWidth * Math.sin((angleDeg * Math.PI) / 180)
}

/** Whether a beam row of Annex C fixes heights or places one beam relative to the opening. */
export type BeamPosition = number | 'halfWidth' | 'halfDiameter'

export interface BeamRow {
  key: string
  beams: number
  positions: readonly BeamPosition[]
  /** Limits on the protected opening; absent fields mean no limit. */
  maxOpeningHeight?: number
  minOpeningHeight?: number
  maxOpeningWidth?: number
  minOpeningWidth?: number
  roundOpening?: { min: number; max: number }
}

const SHARED_BEAM_ROWS: readonly BeamRow[] = [
  { key: '2', beams: 2, positions: [200, 400], maxOpeningHeight: 600 },
  { key: '1-horizontal', beams: 1, positions: [200], maxOpeningHeight: 500, minOpeningWidth: 300 },
  { key: '1-vertical', beams: 1, positions: ['halfWidth'], minOpeningHeight: 500, maxOpeningWidth: 300 },
  { key: '1-round', beams: 1, positions: ['halfDiameter'], roundOpening: { min: 240, max: 500 } },
]

/** Table C.1: beam heights for whole body detection. */
export const BEAM_HEIGHTS: readonly BeamRow[] = [
  { key: '4', beams: 4, positions: [200, 500, 800, 1100] },
  { key: '3', beams: 3, positions: [200, 600, 1000] },
  ...SHARED_BEAM_ROWS,
]

/** Table C.2: alternative heights, industrial use only and only where the risk assessment allows. */
export const BEAM_HEIGHTS_INDUSTRIAL: readonly BeamRow[] = [
  { key: '4', beams: 4, positions: [300, 600, 900, 1200] },
  { key: '3', beams: 3, positions: [300, 700, 1100] },
  ...SHARED_BEAM_ROWS,
]

export interface ReachOverLookup {
  value: number
  /** Index of the column read. */
  column: number
  /** Hazard heights of the rows read, one when H_H is on the grid, two between rows. */
  rows: number[]
  /** H_H and the column value both lie on the grid. */
  exact: boolean
}

/** A reach table read by hazard height (rows) and a height such as H_DT or h_ps (columns). */
export interface ReachGrid {
  columns: readonly number[]
  /** Rows from the highest hazard to the lowest; the first row is all zero. */
  rows: readonly ReachOverRow[]
}

/**
 * Reads a reach grid without interpolating, on the side that gives the
 * larger distance, or returns null when the column value is below the first
 * column, which the table does not cover. A column value between two columns
 * is read in the lower column, which never gives a smaller value because
 * every row falls with the column value. H_H between two rows takes the
 * larger value of both rows, since the columns do not fall steadily with
 * H_H. A hazard at or above the first row cannot be reached at all.
 */
export function lookupGrid(grid: ReachGrid, hazardHeight: number, columnValue: number): ReachOverLookup | null {
  const first = grid.columns[0] as number
  if (!(columnValue >= first)) return null
  let column = 0
  grid.columns.forEach((edge, index) => {
    if (columnValue >= edge) column = index
  })
  const columnExact = grid.columns[column] === columnValue
  const valueAt = (row: ReachOverRow) => row.values[column] ?? 0

  const top = grid.rows[0] as ReachOverRow
  if (hazardHeight >= top.hazardHeight) {
    return { value: 0, column, rows: [top.hazardHeight], exact: columnExact }
  }
  const onGrid = grid.rows.find((row) => row.hazardHeight === hazardHeight)
  if (onGrid) return { value: valueAt(onGrid), column, rows: [onGrid.hazardHeight], exact: columnExact }

  const above = [...grid.rows].reverse().find((row) => row.hazardHeight > hazardHeight) as ReachOverRow
  const below = grid.rows.find((row) => row.hazardHeight < hazardHeight) as ReachOverRow
  return {
    value: Math.max(valueAt(above), valueAt(below)),
    column,
    rows: [below.hazardHeight, above.hazardHeight],
    exact: false,
  }
}

/** The row read for a lookup, the one with the larger value when H_H lies between two rows. */
export function rowRead(grid: ReachGrid, lookup: ReachOverLookup): ReachOverRow | undefined {
  const candidates = grid.rows.filter((row) => lookup.rows.includes(row.hazardHeight))
  return candidates.find((row) => row.values[lookup.column] === lookup.value) ?? candidates[0]
}

/** Table 2 as a grid. */
export const REACH_OVER_GRID: ReachGrid = { columns: REACH_OVER_TOP_EDGES, rows: REACH_OVER }

/**
 * D_DO from Table 2, or null when the top edge is below 900 mm, which the
 * table does not cover. A hazard at or above 2600 mm cannot be reached over
 * the field.
 */
export function lookupReachOver(hazardHeight: number, topEdge: number): ReachOverLookup | null {
  return lookupGrid(REACH_OVER_GRID, hazardHeight, topEdge)
}

export interface HeightLookup {
  value: number
  /** Hazard height of the row read. */
  row: number
  exact: boolean
}

/**
 * Reads a table whose reach distance falls as the hazard height rises. H_H
 * between two rows is read in the lower row, which gives the larger value;
 * above the last row the last value applies.
 */
export function lookupByHazardHeight(table: readonly HeightRow[], hazardHeight: number): HeightLookup {
  let match = table[0] as HeightRow
  for (const row of table) {
    if (hazardHeight >= row.hazardHeight) match = row
  }
  return { value: match.reach, row: match.hazardHeight, exact: match.hazardHeight === hazardHeight }
}
