import { cell, dataTable, footnote, group, onNewPage, section, subheading, withUnit } from '@/shared/reports'
import type { Content, ReportTranslate, TableCell } from '@/shared/reports'
import { referenceTables } from './referenceTables'
import type { ReferenceTable } from './referenceTables'
import { P } from './reportText'
import type { SafetyDistanceInputs } from './types'

/**
 * The appendix of the Safety Distance report: the reference tables the mode
 * reads, with the row and column the calculation used marked and the value
 * it read highlighted.
 */

function referenceTable(table: ReferenceTable): Content {
  const rows: TableCell[][] = table.rows.map((row) => {
    const isActive = row.key === table.activeRow
    return [
      isActive ? cell(row.label, { style: 'cellMarkedHeader' }) : row.label,
      ...row.cells.map((value, index) => {
        if (isActive && index === table.activeColumn) return cell(value, { style: 'cellHit' })
        if (isActive || index === table.activeColumn) return cell(value, { style: 'cellMarked' })
        return value
      }),
    ]
  })
  return group(
    [
      subheading(withUnit(table.title, table.unit)),
      dataTable(
        [{ header: table.rowHeader }, ...table.columns.map((column) => ({ header: column, align: 'right' as const }))],
        rows,
        table.columns.length > 8 ? 'compact' : 'small',
      ),
      footnote(table.note),
    ],
    'after',
  )
}

/** The reference tables on a new page; `fixed` formats with exactly the given decimals. */
export function appendixSection(
  inputs: SafetyDistanceInputs,
  t: ReportTranslate,
  fixed: (value: number, digits: number) => string,
): Content[] {
  const tables = referenceTables(inputs, t, fixed).map(referenceTable)
  if (tables.length === 0) return []
  return [onNewPage(section(t(`${P}.report.appendix`), ...tables))]
}
