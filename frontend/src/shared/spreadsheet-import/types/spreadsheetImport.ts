// Types shared by every spreadsheet import. Nothing in shared/spreadsheet-import
// may import from features.
import type { Schemas } from '@/core/api/generated'

export type DataImportType = Schemas['DataImportType']
export type DataImportProfile = Schemas['DataImportProfileResponse']

/**
 * One field a spreadsheet column can be mapped to. `payloadKey` is the key
 * on the row sent to the backend and also the key of the field's column
 * names in the import profile; `key` is the import's own name for the field
 * (labels, mapping state). `alwaysRequired` fields must be found in the
 * header row for the header to be accepted without a manual mapping.
 */
export interface ImportFieldSpec<K extends string> {
  key: K
  payloadKey: string
  kind: 'text' | 'number' | 'date'
  alwaysRequired?: boolean
}

export type ColumnMapping<K extends string> = Partial<Record<K, string | null>>

/** The header and data rows found in a sheet. Rows are keyed by header text. */
export interface SpreadsheetTable {
  headers: string[]
  rows: Record<string, unknown>[]
  /** 1-based row number of the header in the sheet. */
  headerRow: number
}

export type SpreadsheetImportErrorCode = 'emptyFile' | 'headerNotFound' | 'tooManyRows'

/**
 * A sheet the import cannot use as it is. `missing` names the payload keys
 * of the required fields no header row matched, `limit` and `count` describe
 * a row limit breach.
 */
export class SpreadsheetImportError extends Error {
  readonly code: SpreadsheetImportErrorCode
  readonly missing: string[]
  readonly limit: number | null
  readonly count: number | null

  constructor(
    code: SpreadsheetImportErrorCode,
    details: { missing?: string[]; limit?: number; count?: number } = {},
  ) {
    super(code)
    this.name = 'SpreadsheetImportError'
    this.code = code
    this.missing = details.missing ?? []
    this.limit = details.limit ?? null
    this.count = details.count ?? null
  }
}
