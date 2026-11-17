import type { SpreadsheetCell, SpreadsheetColumn } from '../types/spreadsheetExport'

/** A table column as the column stores describe it: its row field and translated header. */
export interface TableColumnRef<TField extends string> {
  field: TField
  header: string
}

export interface TableExportColumnsOptions<TRow, TField extends string> {
  visibleColumns: readonly TableColumnRef<TField>[]
  /** How a column whose table cell renders more than its raw value is written. */
  cells?: Partial<Record<TField, (row: TRow) => SpreadsheetCell>>
  /** An extra column written right after a field, such as the person beside a date. */
  after?: Partial<Record<TField, SpreadsheetColumn<TRow>>>
  /** Columns that have nothing a spreadsheet can hold, such as a picture. */
  skip?: ReadonlySet<TField>
  /** Columns written after the table's own, such as the link to the record. */
  trailing?: readonly SpreadsheetColumn<TRow>[]
}

function rawCell(value: unknown): SpreadsheetCell {
  return typeof value === 'string' || typeof value === 'number' ? value : null
}

/**
 * The export columns of a table: its visible columns in their order, each
 * written through its entry in `cells` or as its raw value when that is a
 * string or a number (a field the row lacks, such as a picture column,
 * stays empty), each followed by its `after` column, and then the
 * `trailing` columns.
 */
export function tableExportColumns<TRow extends object, TField extends string>(
  options: TableExportColumnsOptions<TRow, TField>,
): SpreadsheetColumn<TRow>[] {
  const columns: SpreadsheetColumn<TRow>[] = []
  for (const column of options.visibleColumns) {
    if (options.skip?.has(column.field)) continue
    const cell = options.cells?.[column.field]
    columns.push({
      header: column.header,
      value: cell ?? ((row) => rawCell((row as Record<string, unknown>)[column.field])),
    })
    const extra = options.after?.[column.field]
    if (extra) columns.push(extra)
  }
  columns.push(...(options.trailing ?? []))
  return columns
}
