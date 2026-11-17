import type { DataImportProfile, DataImportType } from '../types/spreadsheetImport'

/** An import profile for tests: column names per payload key, defaults otherwise. */
export function makeProfile(
  columnNames: Record<string, string[]>,
  overrides: Partial<Omit<DataImportProfile, 'fields'>> = {},
): DataImportProfile {
  return {
    import_type: 'bought_item_demand' as DataImportType,
    header_row: null,
    data_offset: 1,
    max_rows: 100,
    ...overrides,
    fields: Object.entries(columnNames).map(([key, column_names]) => ({ key, column_names })),
  }
}
