/**
 * Numeric tables of ISO 13857:2019, safety distances against reaching hazard
 * zones with the upper and lower limbs, and their lookups. The tables hold
 * our own transcription of the standard's values. Like ISO 13855 the
 * standard forbids interpolation, so every lookup reads the side that gives
 * the larger distance.
 */
import { lookupGrid } from './tables'
import type { ReachGrid, ReachOverLookup } from './tables'
import type { OpeningShape } from './types'

/** Columns of Table 1: height h_ps of the protective structure. */
const LOW_RISK_HEIGHTS = [1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400, 2500] as const

/** Table 1: reaching over a protective structure where severity and probability of harm are both low. */
export const REACH_OVER_STRUCTURE_LOW_RISK: ReachGrid = {
  columns: LOW_RISK_HEIGHTS,
  rows: [
    { hazardHeight: 2500, values: [0, 0, 0, 0, 0, 0, 0, 0, 0] },
    { hazardHeight: 2400, values: [100, 100, 100, 100, 100, 100, 100, 100, 0] },
    { hazardHeight: 2200, values: [600, 600, 500, 500, 400, 350, 250, 0, 0] },
    { hazardHeight: 2000, values: [1100, 900, 700, 600, 500, 350, 0, 0, 0] },
    { hazardHeight: 1800, values: [1100, 1000, 900, 900, 600, 0, 0, 0, 0] },
    { hazardHeight: 1600, values: [1300, 1000, 900, 900, 500, 0, 0, 0, 0] },
    { hazardHeight: 1400, values: [1300, 1000, 900, 800, 100, 0, 0, 0, 0] },
    { hazardHeight: 1200, values: [1400, 1000, 900, 500, 0, 0, 0, 0, 0] },
    { hazardHeight: 1000, values: [1400, 1000, 900, 300, 0, 0, 0, 0, 0] },
    { hazardHeight: 800, values: [1300, 900, 600, 0, 0, 0, 0, 0, 0] },
    { hazardHeight: 600, values: [1200, 500, 0, 0, 0, 0, 0, 0, 0] },
    { hazardHeight: 400, values: [1200, 300, 0, 0, 0, 0, 0, 0, 0] },
    { hazardHeight: 200, values: [1100, 200, 0, 0, 0, 0, 0, 0, 0] },
    { hazardHeight: 0, values: [1100, 200, 0, 0, 0, 0, 0, 0, 0] },
  ],
}

/** Columns of Table 2: height h_ps of the protective structure. */
const HEIGHTS = [1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400, 2500, 2700] as const

/** Table 2: reaching over a protective structure, the general case. */
export const REACH_OVER_STRUCTURE: ReachGrid = {
  columns: HEIGHTS,
  rows: [
    { hazardHeight: 2700, values: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
    { hazardHeight: 2600, values: [900, 800, 700, 600, 600, 500, 400, 300, 100, 0] },
    { hazardHeight: 2400, values: [1100, 1000, 900, 800, 700, 600, 400, 300, 100, 0] },
    { hazardHeight: 2200, values: [1300, 1200, 1000, 900, 800, 600, 400, 300, 0, 0] },
    { hazardHeight: 2000, values: [1400, 1300, 1100, 900, 800, 600, 400, 0, 0, 0] },
    { hazardHeight: 1800, values: [1500, 1400, 1100, 900, 800, 600, 0, 0, 0, 0] },
    { hazardHeight: 1600, values: [1500, 1400, 1100, 900, 800, 500, 0, 0, 0, 0] },
    { hazardHeight: 1400, values: [1500, 1400, 1100, 900, 800, 0, 0, 0, 0, 0] },
    { hazardHeight: 1200, values: [1500, 1400, 1100, 900, 700, 0, 0, 0, 0, 0] },
    { hazardHeight: 1000, values: [1500, 1400, 1000, 800, 0, 0, 0, 0, 0, 0] },
    { hazardHeight: 800, values: [1500, 1300, 900, 600, 0, 0, 0, 0, 0, 0] },
    { hazardHeight: 600, values: [1400, 1300, 800, 0, 0, 0, 0, 0, 0, 0] },
    { hazardHeight: 400, values: [1400, 1200, 400, 0, 0, 0, 0, 0, 0, 0] },
    { hazardHeight: 200, values: [1200, 900, 0, 0, 0, 0, 0, 0, 0, 0] },
    { hazardHeight: 0, values: [1100, 500, 0, 0, 0, 0, 0, 0, 0, 0] },
  ],
}

/** Lower structures do not restrain the body enough and are not covered (Tables 1 and 2). */
export const MIN_STRUCTURE_HEIGHT = 1000
/** Lower structures need additional protective measures (Table 2, 4.4). */
export const STRUCTURE_HEIGHT_WITHOUT_MEASURES = 1400
/** From this height a hazard is out of reach upwards (4.2.1.2); for low risk the first row of Table 1. */
export const OUT_OF_REACH_HEIGHT = 2700

/**
 * The horizontal safety distance s_h for reaching over a structure of height
 * h_ps, or null for a structure below 1000 mm. Above the last column the last
 * column applies.
 */
export function lookupStructure(hazardHeight: number, structureHeight: number, lowRisk: boolean): ReachOverLookup | null {
  return lookupGrid(lowRisk ? REACH_OVER_STRUCTURE_LOW_RISK : REACH_OVER_STRUCTURE, hazardHeight, structureHeight)
}

/**
 * The lowest tabulated structure height whose safety distance does not
 * exceed the given horizontal distance (Annex A, example 1), or null when no
 * column of the table is enough.
 */
export function lowestStructureHeight(hazardHeight: number, distance: number, lowRisk: boolean): number | null {
  const grid = lowRisk ? REACH_OVER_STRUCTURE_LOW_RISK : REACH_OVER_STRUCTURE
  for (const height of grid.columns) {
    const lookup = lookupGrid(grid, hazardHeight, height)
    if (lookup && lookup.value <= distance) return height
  }
  return null
}

/** The body part an opening lets through, as the tables name it. */
export type OpeningBodyPart = 'fingertip' | 'finger' | 'hand' | 'arm' | 'toeTip' | 'toe' | 'foot' | 'legKnee' | 'legCrotch'

/**
 * One row of an opening table: openings up to `max` (above the previous
 * row's `max`), the body part that gets through and the safety distance per
 * shape. Table 7 lists square and round together; null means the opening is
 * not permitted.
 */
export interface OpeningRow {
  max: number
  part: OpeningBodyPart
  slot: number | null
  square: number
  round: number
}

/** The footnote of an opening table that lets a short slot have a smaller distance. */
export interface ShortSlot {
  /** Longest slot the reduction applies to. */
  maxLength: number
  /** The row it applies to, by its `max`. */
  row: number
  value: number
}

export interface OpeningTable {
  /** Clause and table number in ISO 13857:2019. */
  clause: string
  table: string
  rows: readonly OpeningRow[]
  shortSlot: ShortSlot
}

/** Table 4: reaching through regular openings, persons 14 years and older. */
export const OPENINGS_UPPER: OpeningTable = {
  clause: '4.2.4.1',
  table: '4',
  rows: [
    { max: 4, part: 'fingertip', slot: 2, square: 2, round: 2 },
    { max: 6, part: 'fingertip', slot: 10, square: 5, round: 5 },
    { max: 8, part: 'finger', slot: 20, square: 15, round: 5 },
    { max: 10, part: 'finger', slot: 80, square: 25, round: 20 },
    { max: 12, part: 'hand', slot: 100, square: 80, round: 80 },
    { max: 20, part: 'hand', slot: 120, square: 120, round: 120 },
    { max: 30, part: 'hand', slot: 850, square: 120, round: 120 },
    { max: 40, part: 'arm', slot: 850, square: 200, round: 120 },
    { max: 120, part: 'arm', slot: 850, square: 850, round: 850 },
  ],
  shortSlot: { maxLength: 65, row: 30, value: 200 },
}

/** Table 5: reaching through regular openings, persons 3 years and older. */
export const OPENINGS_CHILDREN: OpeningTable = {
  clause: '4.2.4.2',
  table: '5',
  rows: [
    { max: 4, part: 'fingertip', slot: 2, square: 2, round: 2 },
    { max: 6, part: 'fingertip', slot: 20, square: 10, round: 10 },
    { max: 8, part: 'finger', slot: 40, square: 30, round: 20 },
    { max: 10, part: 'finger', slot: 80, square: 60, round: 60 },
    { max: 12, part: 'hand', slot: 100, square: 80, round: 80 },
    { max: 20, part: 'hand', slot: 900, square: 120, round: 120 },
    { max: 30, part: 'arm', slot: 900, square: 550, round: 120 },
    { max: 100, part: 'arm', slot: 900, square: 900, round: 900 },
  ],
  shortSlot: { maxLength: 40, row: 20, value: 120 },
}

/** Table 7: reaching through regular openings with the lower limbs, persons 14 years and older. */
export const OPENINGS_LOWER: OpeningTable = {
  clause: '4.3',
  table: '7',
  rows: [
    { max: 5, part: 'toeTip', slot: 0, square: 0, round: 0 },
    { max: 15, part: 'toeTip', slot: 10, square: 0, round: 0 },
    { max: 35, part: 'toe', slot: 80, square: 25, round: 25 },
    { max: 60, part: 'foot', slot: 180, square: 80, round: 80 },
    { max: 80, part: 'foot', slot: 650, square: 180, round: 180 },
    { max: 95, part: 'legKnee', slot: 1100, square: 650, round: 650 },
    { max: 180, part: 'legCrotch', slot: 1100, square: 1100, round: 1100 },
    { max: 240, part: 'legCrotch', slot: null, square: 1100, round: 1100 },
  ],
  shortSlot: { maxLength: 75, row: 35, value: 50 },
}

/** Slots wider than this, and squares or circles larger than the next, let the whole body through (4.4). */
export const WHOLE_BODY_SLOT = 180
export const WHOLE_BODY_SQUARE = 240

export function wholeBodyLimit(shape: OpeningShape): number {
  return shape === 'slot' ? WHOLE_BODY_SLOT : WHOLE_BODY_SQUARE
}

export interface OpeningLookup {
  /** The safety distance, or null when the opening is not permitted. */
  value: number | null
  /** Index of the row read. */
  row: number
  /** The short slot footnote reduced the value. */
  reduced: boolean
}

/** The largest opening a table covers. */
export function tableLimit(table: OpeningTable): number {
  return (table.rows[table.rows.length - 1] as OpeningRow).max
}

/**
 * The safety distance for an opening of size e, or null when e is beyond the
 * table. The rows are closed at the top, so e = 6 mm is read in the row
 * 4 < e ≤ 6. A slot no longer than the footnote's length gets its smaller
 * value in the row the footnote names.
 */
export function lookupOpening(
  table: OpeningTable,
  shape: OpeningShape,
  e: number,
  slotLength: number | null = null,
): OpeningLookup | null {
  const row = table.rows.findIndex((r) => e <= r.max)
  if (row < 0) return null
  const entry = table.rows[row] as OpeningRow
  const value = entry[shape]
  const short = table.shortSlot
  if (shape === 'slot' && value !== null && slotLength !== null && slotLength <= short.maxLength && entry.max === short.row) {
    return { value: Math.min(value, short.value), row, reduced: true }
  }
  return { value, row, reduced: false }
}
