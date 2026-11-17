import { isCalendarDate, parseBackendTimestamp, todayKey, zonedParts } from '@/core/utils/dates'

import type { SpreadsheetCell, SpreadsheetColumn } from '../types/spreadsheetExport'

/**
 * A cell in the shape SheetJS writes, declared here so the worksheet can be
 * built and tested without loading the xlsx package at all.
 */
export interface WorksheetCell {
  t: 's' | 'n'
  v: string | number
  z?: string
  l?: { Target: string }
}

/** The cells of a worksheet keyed by address (`A1`), its range and its column widths. */
export interface WorksheetData {
  cells: Record<string, WorksheetCell>
  ref: string
  widths: number[]
}

/** The number formats of date cells, which Excel and LibreOffice both show as is. */
export const DATE_CELL_FORMAT = 'yyyy-mm-dd'
export const DATE_TIME_CELL_FORMAT = 'yyyy-mm-dd hh:mm'

const MIN_COLUMN_WIDTH = 8
const MAX_COLUMN_WIDTH = 60

const MS_PER_DAY = 86_400_000
const EXCEL_EPOCH_UTC = Date.UTC(1899, 11, 30)

function serial(year: number, month: number, day: number, hour = 0, minute = 0): number {
  return (Date.UTC(year, month - 1, day, hour, minute) - EXCEL_EPOCH_UTC) / MS_PER_DAY
}

/**
 * The spreadsheet date cell of an API date. A spreadsheet date has no time
 * zone, so a timestamp is written as the wall clock time it shows in
 * `timeZone`, the same time the tables show, and a bare calendar date as that
 * day. Undefined for a value that is no valid date.
 */
export function toDateCell(iso: string, timeZone: string): WorksheetCell | undefined {
  if (isCalendarDate(iso)) {
    const [year, month, day] = iso.split('-').map(Number)
    if (!year || !month || !day) return undefined
    return { t: 'n', v: serial(year, month, day), z: DATE_CELL_FORMAT }
  }
  const date = parseBackendTimestamp(iso)
  if (Number.isNaN(date.getTime())) return undefined
  const parts = zonedParts(date, timeZone)
  return {
    t: 'n',
    v: serial(
      Number(parts.year),
      Number(parts.month),
      Number(parts.day),
      Number(parts.hour),
      Number(parts.minute),
    ),
    z: DATE_TIME_CELL_FORMAT,
  }
}

/** The A1 style address of a zero based row and column. */
export function cellAddress(row: number, column: number): string {
  let letters = ''
  for (let n = column + 1; n > 0; n = Math.floor((n - 1) / 26)) {
    letters = String.fromCharCode(65 + ((n - 1) % 26)) + letters
  }
  return `${letters}${row + 1}`
}

function toWorksheetCell(value: SpreadsheetCell, timeZone: string): WorksheetCell | undefined {
  if (value === null || value === '') return undefined
  if (typeof value === 'string') return { t: 's', v: value }
  if (typeof value === 'number') return Number.isFinite(value) ? { t: 'n', v: value } : undefined
  if ('iso' in value) return toDateCell(value.iso, timeZone)
  if ('format' in value) {
    return Number.isFinite(value.value) ? { t: 'n', v: value.value, z: value.format } : undefined
  }
  return { t: 's', v: value.text, l: { Target: value.url } }
}

function displayLength(cell: WorksheetCell): number {
  if (cell.z === DATE_CELL_FORMAT || cell.z === DATE_TIME_CELL_FORMAT) return cell.z.length
  return String(cell.v).length
}

/**
 * The worksheet of an export: the header row, then one row per item in the
 * given order, with each column as wide as its longest value within sensible
 * bounds. Empty values leave their cell out, so the sheet has no stub cells.
 */
export function buildWorksheet<TRow>(
  rows: readonly TRow[],
  columns: readonly SpreadsheetColumn<TRow>[],
  timeZone: string,
): WorksheetData {
  const cells: Record<string, WorksheetCell> = {}
  const widths = columns.map((column) => column.header.length)

  columns.forEach((column, c) => {
    cells[cellAddress(0, c)] = { t: 's', v: column.header }
  })

  rows.forEach((row, r) => {
    columns.forEach((column, c) => {
      const cell = toWorksheetCell(column.value(row), timeZone)
      if (!cell) return
      cells[cellAddress(r + 1, c)] = cell
      widths[c] = Math.max(widths[c] ?? 0, displayLength(cell))
    })
  })

  const lastColumn = Math.max(columns.length - 1, 0)
  return {
    cells,
    ref: `A1:${cellAddress(rows.length, lastColumn)}`,
    widths: widths.map((width) => Math.min(Math.max(width + 2, MIN_COLUMN_WIDTH), MAX_COLUMN_WIDTH)),
  }
}

/**
 * A sheet name Excel accepts: at most 31 characters and none of the
 * characters it reserves.
 */
export function toSheetName(name: string): string {
  const cleaned = name.replace(/[\\/?*:[\]]/g, ' ').trim()
  return (cleaned || 'Sheet1').slice(0, 31)
}

/**
 * The download name of an export, such as `bought-items_2026-11-12.xlsx`,
 * dated by today in the display time zone. Spaces and characters a file
 * system rejects become a hyphen.
 */
export function exportFilename(prefix: string, now: Date = new Date()): string {
  const safePrefix = prefix.replace(/[\\/:*?"<>|\s]+/g, '-')
  return `${safePrefix}_${todayKey(now)}.xlsx`
}
