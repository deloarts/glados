/**
 * Builds and downloads a product's PLC tag table in the layout its PLC
 * environment names: one column per export column, in that order, on the
 * environment's sheet. Split into a pure row builder and a thin writer that
 * keeps the SheetJS import dynamic, like the PDM reconciliation export.
 */
import { downloadBlob } from '@/core/utils/downloadBlob'

import type { PlcExportColumn, PlcTag, PlcTagList } from '../types/productDevice'

function cell(tag: PlcTag, column: PlcExportColumn): string {
  switch (column.source) {
    case 'tag_name':
      return tag.name
    case 'tag_table':
      return tag.tag_table
    case 'data_type':
      return tag.data_type
    case 'address':
      return tag.address ?? ''
    case 'comment':
      return tag.comment
    case 'device_name':
      return tag.device_name
    case 'device_name_ascii':
      return tag.device_name_ascii
    case 'signal_type':
      return tag.signal_type
    case 'safety':
      return tag.safety ? 'True' : 'False'
    case 'constant':
      return column.value ?? ''
  }
}

/** The header row and one row per tag. */
export function buildPlcTagRows(list: PlcTagList): string[][] {
  const columns = list.environment?.export_columns ?? []
  return [columns.map((column) => column.header), ...list.tags.map((tag) => columns.map((column) => cell(tag, column)))]
}

export async function writePlcTagExportFile(list: PlcTagList, productNumber: string): Promise<void> {
  const XLSX = await import('xlsx')
  const worksheet = XLSX.utils.aoa_to_sheet(buildPlcTagRows(list))
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, list.environment?.export_sheet || 'PLC Tags')
  const buffer = XLSX.write(workbook, { type: 'array', bookType: 'xlsx' }) as ArrayBuffer
  downloadBlob(
    new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }),
    `${productNumber}_PLC_Tags.xlsx`,
  )
}
