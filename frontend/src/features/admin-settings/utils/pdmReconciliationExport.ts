/**
 * Builds and downloads the reconciliation dialog's Excel export. Split into a
 * pure row-builder (easy to unit-test without touching the xlsx package at
 * all) and a thin writer that only exists to keep the SheetJS import
 * dynamic, like readSheetGrid.ts does: the full build would otherwise ship
 * to every admin-settings visitor whether or not they ever open this dialog.
 */
import { downloadBlob } from '@/core/utils/downloadBlob'

import type { PdmFileKind, PdmReconciliationFinding } from '../types/adminSettingsTypes'

export interface PdmReconciliationExportRow {
  category: string
  severity: string
  kind: string
  partNumber: string
  revision: string
  message: string
  count: number
}

/** The fixed column order of the export. */
export const PDM_RECONCILIATION_EXPORT_COLUMNS: (keyof PdmReconciliationExportRow)[] = [
  'category',
  'severity',
  'kind',
  'partNumber',
  'revision',
  'message',
  'count',
]

/** The translated header row, the sheet name and the file name of the export. */
export interface PdmReconciliationExportFormat {
  headers: Record<keyof PdmReconciliationExportRow, string>
  sheetName: string
  filename: string
}

export interface PdmReconciliationExportLabels {
  category: (category: string) => string
  severity: (severity: string) => string
  kind: (kind: PdmFileKind | null) => string
}

/**
 * One row per finding, in the fixed column order the dialog's export
 * button promises. `part_number`/`revision` are kept as two separate
 * columns here (unlike the findings table's combined label) since a
 * spreadsheet is exactly the place someone wants to filter/sort on either
 * one alone.
 */
export function buildPdmReconciliationExportRows(
  findings: PdmReconciliationFinding[],
  labels: PdmReconciliationExportLabels,
): PdmReconciliationExportRow[] {
  return findings.map((finding) => ({
    category: labels.category(finding.category),
    severity: labels.severity(finding.severity),
    kind: labels.kind(finding.kind),
    partNumber: finding.part_number ?? '',
    revision: finding.revision ?? '',
    message: finding.message,
    count: finding.count,
  }))
}

/**
 * Writes `rows` under the translated header row to a single-sheet .xlsx
 * workbook and triggers a browser download. The actual SheetJS call, kept
 * separate from buildPdmReconciliationExportRows so a spec can assert on the
 * built rows without mocking the xlsx package at all, and can mock this one
 * function alone to assert the export was triggered.
 */
export async function writePdmReconciliationExportFile(
  rows: PdmReconciliationExportRow[],
  format: PdmReconciliationExportFormat,
): Promise<void> {
  const XLSX = await import('xlsx')
  const worksheet = XLSX.utils.aoa_to_sheet([
    PDM_RECONCILIATION_EXPORT_COLUMNS.map((column) => format.headers[column]),
    ...rows.map((row) => PDM_RECONCILIATION_EXPORT_COLUMNS.map((column) => row[column])),
  ])
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, format.sheetName)
  const buffer = XLSX.write(workbook, { type: 'array', bookType: 'xlsx' }) as ArrayBuffer
  downloadBlob(
    new Blob([buffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }),
    format.filename,
  )
}
