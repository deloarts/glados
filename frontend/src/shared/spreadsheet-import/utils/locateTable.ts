import { columnNameIndex, headerText, normalizeColumnName } from './columnNames'
import { SpreadsheetImportError } from '../types/spreadsheetImport'

import type {
  DataImportProfile,
  ImportFieldSpec,
  SpreadsheetTable,
} from '../types/spreadsheetImport'

/** How many non-empty rows automatic header detection looks at. */
export const HEADER_SCAN_ROWS = 20

function isEmptyCell(value: unknown): boolean {
  return value === null || value === undefined || (typeof value === 'string' && !value.trim())
}

function isEmptyRow(row: unknown[] | undefined): boolean {
  return !row || row.every(isEmptyCell)
}

/** How many distinct fields the cells of a row name. */
function headerScore(row: unknown[], index: Map<string, string>): number {
  const matched = new Set<string>()
  for (const cell of row) {
    const field = index.get(normalizeColumnName(cell))
    if (field) matched.add(field)
  }
  return matched.size
}

/**
 * The 0-based index of the header row. A fixed row from the profile is
 * taken as it is; otherwise the first non-empty rows are scored by how many
 * fields their cells name and the best one wins, the earliest on a tie. A
 * sheet where no scanned row names any field has no recognisable header.
 */
function findHeaderRow(
  grid: unknown[][],
  profile: DataImportProfile,
  index: Map<string, string>,
  required: string[],
): number {
  if (profile.header_row !== null) {
    const fixed = profile.header_row - 1
    if (isEmptyRow(grid[fixed])) {
      throw new SpreadsheetImportError('headerNotFound', { missing: required })
    }
    return fixed
  }

  let best = -1
  let bestScore = 0
  let scanned = 0
  for (let i = 0; i < grid.length && scanned < HEADER_SCAN_ROWS; i++) {
    const row = grid[i]
    if (isEmptyRow(row)) continue
    scanned++
    const score = headerScore(row!, index)
    if (score > bestScore) {
      best = i
      bestScore = score
    }
  }
  if (best < 0) {
    throw new SpreadsheetImportError('headerNotFound', { missing: required })
  }
  return best
}

/**
 * Finds the header and data rows of a sheet as the import profile
 * describes them. Header cells become the column names, made unique with a
 * counter when a sheet repeats one; columns without a header are dropped.
 * Data starts `data_offset` rows below the header, completely empty rows are
 * skipped wherever they are, and more data rows than the profile's limit
 * refuse the file.
 */
export function locateTable<K extends string>(
  grid: unknown[][],
  profile: DataImportProfile,
  fields: ImportFieldSpec<K>[],
): SpreadsheetTable {
  if (grid.every((row) => isEmptyRow(row))) {
    throw new SpreadsheetImportError('emptyFile')
  }

  const index = columnNameIndex(profile)
  const required = fields.filter((f) => f.alwaysRequired).map((f) => f.payloadKey)
  const headerIndex = findHeaderRow(grid, profile, index, required)
  const headerCells = grid[headerIndex] ?? []

  const columns: { column: number; header: string }[] = []
  const seen = new Map<string, number>()
  headerCells.forEach((cell, column) => {
    const text = headerText(cell)
    if (!text) return
    const count = (seen.get(text) ?? 0) + 1
    seen.set(text, count)
    columns.push({ column, header: count === 1 ? text : `${text} (${count})` })
  })

  const rows: Record<string, unknown>[] = []
  for (let i = headerIndex + profile.data_offset; i < grid.length; i++) {
    const cells = grid[i]
    if (!cells || columns.every(({ column }) => isEmptyCell(cells[column]))) continue
    const record: Record<string, unknown> = {}
    for (const { column, header } of columns) {
      record[header] = cells[column] ?? null
    }
    rows.push(record)
  }

  if (rows.length === 0) {
    throw new SpreadsheetImportError('emptyFile')
  }
  if (rows.length > profile.max_rows) {
    throw new SpreadsheetImportError('tooManyRows', {
      limit: profile.max_rows,
      count: rows.length,
    })
  }

  return {
    headers: columns.map((c) => c.header),
    rows,
    headerRow: headerIndex + 1,
  }
}
