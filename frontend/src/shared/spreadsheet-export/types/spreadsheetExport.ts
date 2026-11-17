/** A cell that opens `url` when clicked and shows `text`. */
export interface SpreadsheetLink {
  text: string
  url: string
}

/**
 * A date or timestamp as the API sends it. A bare `YYYY-MM-DD` is written as
 * a calendar date, a timestamp as date and time in the display time zone.
 */
export interface SpreadsheetDate {
  iso: string
}

/** A number shown with a spreadsheet number format, such as two decimals for a price. */
export interface SpreadsheetNumber {
  value: number
  format: string
}

/**
 * The value of one exported cell. A string stays text even when it looks like
 * a number, so part numbers and GTINs keep their leading zeros, a number and a
 * date are written as real spreadsheet numbers and dates, and null leaves the
 * cell empty.
 */
export type SpreadsheetCell =
  | string
  | number
  | SpreadsheetNumber
  | SpreadsheetDate
  | SpreadsheetLink
  | null

/** One column of an export: its translated header and how a row fills it. */
export interface SpreadsheetColumn<TRow> {
  header: string
  value: (row: TRow) => SpreadsheetCell
}

/** The name of the single sheet and the file name of the download. */
export interface SpreadsheetFormat {
  sheetName: string
  filename: string
}

/** Which rows an export covers: every row of the current filter or the checked ones. */
export type SpreadsheetExportScope = 'filtered' | 'selected'
