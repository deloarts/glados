import { downloadBlob } from '@/core/utils/downloadBlob'

import type { WorkSheet } from 'xlsx'

import type { SpreadsheetFormat } from '../types/spreadsheetExport'
import { toSheetName, type WorksheetData } from './buildWorksheet'

const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

/**
 * Writes `worksheet` as the single sheet of an .xlsx workbook, with an
 * autofilter over the header row, and triggers the download. SheetJS is
 * imported dynamically so its full build only loads once someone exports,
 * see parseExcelDemandsFile.ts for the same reasoning.
 */
export async function writeSpreadsheetFile(
  worksheet: WorksheetData,
  format: SpreadsheetFormat,
): Promise<void> {
  const XLSX = await import('xlsx')
  const sheet: Record<string, unknown> = {
    ...worksheet.cells,
    '!ref': worksheet.ref,
    '!autofilter': { ref: worksheet.ref },
    '!cols': worksheet.widths.map((wch) => ({ wch })),
  }
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(
    workbook,
    sheet as WorkSheet,
    toSheetName(format.sheetName),
  )
  const buffer = XLSX.write(workbook, { type: 'array', bookType: 'xlsx' }) as ArrayBuffer
  downloadBlob(new Blob([buffer], { type: XLSX_MIME }), format.filename)
}
