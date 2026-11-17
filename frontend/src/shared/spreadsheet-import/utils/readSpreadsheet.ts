import { getDataImportProfile } from '../api/getDataImportProfile'
import { autoMapColumns } from './columnMapping'
import { locateTable } from './locateTable'
import { readSheetGrid } from './readSheetGrid'

import type {
  ColumnMapping,
  DataImportType,
  ImportFieldSpec,
  SpreadsheetTable,
} from '../types/spreadsheetImport'

export interface ReadSpreadsheetResult<K extends string> extends SpreadsheetTable {
  mapping: ColumnMapping<K>
}

/**
 * The upload step every import shares: load the import's profile, read the
 * sheet, find its header and data rows, and map the columns by the
 * profile's column names. Throws SpreadsheetImportError for a sheet the
 * import cannot use; any other error means the file could not be read.
 */
export async function readSpreadsheet<K extends string>(
  file: File,
  importType: DataImportType,
  fields: ImportFieldSpec<K>[],
): Promise<ReadSpreadsheetResult<K>> {
  const profile = await getDataImportProfile(importType)
  const grid = await readSheetGrid(file)
  const table = locateTable(grid, profile, fields)
  return { ...table, mapping: autoMapColumns(table.headers, fields, profile) }
}
