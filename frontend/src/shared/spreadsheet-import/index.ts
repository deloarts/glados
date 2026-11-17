// Public surface of the shared spreadsheet import: the upload step every
// import runs (profile, parse, header detection, column mapping) and the
// value coercion of mapped cells, plus the upload drop zone and the manual
// mapping step. Each import keeps its own dialog and store.
export { getDataImportProfile } from './api/getDataImportProfile'
export { default as SpreadsheetColumnNamesButton } from './components/SpreadsheetColumnNamesButton.vue'
export { default as SpreadsheetDropzone } from './components/SpreadsheetDropzone.vue'
export { default as SpreadsheetMappingStep } from './components/SpreadsheetMappingStep.vue'
export {
  autoMapColumns,
  buildRowsFromMapping,
  hasRequiredColumns,
  toDateString,
  toNumber,
  toText,
} from './utils/columnMapping'
export { headerText, normalizeColumnName } from './utils/columnNames'
export { HEADER_SCAN_ROWS, locateTable } from './utils/locateTable'
export { readSheetGrid } from './utils/readSheetGrid'
export { readSpreadsheet } from './utils/readSpreadsheet'
export { SpreadsheetImportError } from './types/spreadsheetImport'

export type { ReadSpreadsheetResult } from './utils/readSpreadsheet'
export type {
  ColumnMapping,
  DataImportProfile,
  DataImportType,
  ImportFieldSpec,
  SpreadsheetImportErrorCode,
  SpreadsheetTable,
} from './types/spreadsheetImport'
