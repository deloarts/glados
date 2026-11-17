// Public surface of the shared spreadsheet export: the Export button of a
// controls bar, the composable that reads the filtered rows and writes the
// file, and the cell helpers a feature builds its columns with. Each table
// keeps its own column list.
export { default as SpreadsheetExportButton } from './components/SpreadsheetExportButton.vue'
export { useSpreadsheetExport } from './composables/useSpreadsheetExport'
export { exportFilename } from './utils/buildWorksheet'
export { dateCell, listCell, moneyCell, recordLinkCell, urlCell } from './utils/cells'
export { tableExportColumns } from './utils/tableColumns'
export { EXPORT_CONFIRM_ROWS, EXPORT_MAX_ROWS } from './utils/fetchExportRows'

export type { SpreadsheetExportSource } from './composables/useSpreadsheetExport'
export type { TableColumnRef, TableExportColumnsOptions } from './utils/tableColumns'
export type {
  SpreadsheetCell,
  SpreadsheetColumn,
  SpreadsheetDate,
  SpreadsheetExportScope,
  SpreadsheetFormat,
  SpreadsheetLink,
  SpreadsheetNumber,
} from './types/spreadsheetExport'
