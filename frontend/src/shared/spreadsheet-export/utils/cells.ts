import type { SpreadsheetCell } from '../types/spreadsheetExport'

/** A date cell for an API date or timestamp, empty without one. */
export function dateCell(iso: string | null | undefined): SpreadsheetCell {
  return iso ? { iso } : null
}

/** A clickable cell for a web address, empty without one. */
export function urlCell(url: string | null | undefined): SpreadsheetCell {
  return url ? { text: url, url } : null
}

/**
 * The lasting link to a record, its public id through the app's Resolve
 * page, the same link the Share button copies. The address bar's link holds
 * the database id, which points at another record after a restore, so a
 * file that is kept around links the public id instead.
 */
export function recordLinkCell(publicId: string): SpreadsheetCell {
  const url = new URL(
    `${import.meta.env.BASE_URL}resolve/${encodeURIComponent(publicId)}`,
    window.location.origin,
  ).href
  return { text: url, url }
}

/** The number format of a money cell: thousands separated, two decimals. */
export const MONEY_CELL_FORMAT = '#,##0.00'

/**
 * A money cell for an amount the API sends in cents, as a number with two
 * decimals, empty without one. The currency goes into the column header.
 */
export function moneyCell(cents: number | null | undefined): SpreadsheetCell {
  return cents === null || cents === undefined ? null : { value: cents / 100, format: MONEY_CELL_FORMAT }
}

/** Several values in one text cell, comma separated, empty without any. */
export function listCell(values: readonly (string | null | undefined)[]): SpreadsheetCell {
  return values.filter((value): value is string => !!value).join(', ') || null
}
