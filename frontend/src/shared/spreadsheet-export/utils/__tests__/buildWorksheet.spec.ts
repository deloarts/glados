import { describe, expect, it } from 'vitest'

import {
  DATE_CELL_FORMAT,
  DATE_TIME_CELL_FORMAT,
  buildWorksheet,
  cellAddress,
  exportFilename,
  toDateCell,
  toSheetName,
} from '../buildWorksheet'

import type { SpreadsheetColumn } from '../../types/spreadsheetExport'

interface Row {
  id: number
  code: string
  created: string | null
  url: string | null
}

const COLUMNS: SpreadsheetColumn<Row>[] = [
  { header: 'ID', value: (row) => row.id },
  { header: 'Code', value: (row) => row.code },
  { header: 'Created', value: (row) => (row.created ? { iso: row.created } : null) },
  { header: 'Link', value: (row) => (row.url ? { text: row.url, url: row.url } : null) },
]

describe('cellAddress', () => {
  it('names columns past Z with two letters', () => {
    expect(cellAddress(0, 0)).toBe('A1')
    expect(cellAddress(4, 25)).toBe('Z5')
    expect(cellAddress(0, 26)).toBe('AA1')
    expect(cellAddress(9, 701)).toBe('ZZ10')
    expect(cellAddress(0, 702)).toBe('AAA1')
  })
})

describe('toDateCell', () => {
  it('writes a timestamp as the wall clock time of the display time zone', () => {
    // 2026-11-12 09:30 UTC is 10:30 in Vienna, 46338 days after the Excel epoch.
    const cell = toDateCell('2026-11-12T09:30:00Z', 'Europe/Vienna')

    expect(cell?.t).toBe('n')
    expect(cell?.z).toBe(DATE_TIME_CELL_FORMAT)
    expect(cell?.v).toBeCloseTo(46338 + 10.5 / 24, 8)
  })

  it('reads a timestamp without an offset as UTC, as the API means it', () => {
    expect(toDateCell('2026-11-12T09:30:00', 'UTC')?.v).toBeCloseTo(46338 + 9.5 / 24, 8)
  })

  it('writes a calendar date as that day whatever the time zone', () => {
    const cell = toDateCell('2026-11-12', 'America/New_York')

    expect(cell).toEqual({ t: 'n', v: 46338, z: DATE_CELL_FORMAT })
  })

  it('leaves an invalid date empty', () => {
    expect(toDateCell('not-a-dateT', 'UTC')).toBeUndefined()
  })
})

describe('buildWorksheet', () => {
  it('writes the header row and keeps text that looks like a number as text', () => {
    const sheet = buildWorksheet(
      [{ id: 7, code: '000123', created: null, url: null }],
      COLUMNS,
      'UTC',
    )

    expect(sheet.cells.A1).toEqual({ t: 's', v: 'ID' })
    expect(sheet.cells.D1).toEqual({ t: 's', v: 'Link' })
    expect(sheet.cells.A2).toEqual({ t: 'n', v: 7 })
    expect(sheet.cells.B2).toEqual({ t: 's', v: '000123' })
    expect(sheet.ref).toBe('A1:D2')
  })

  it('leaves empty values out instead of writing stub cells', () => {
    const sheet = buildWorksheet([{ id: 1, code: '', created: null, url: null }], COLUMNS, 'UTC')

    expect(sheet.cells.B2).toBeUndefined()
    expect(sheet.cells.C2).toBeUndefined()
    expect(sheet.cells.D2).toBeUndefined()
  })

  it('writes a link as text with its target', () => {
    const url = 'https://example.com/part'
    const sheet = buildWorksheet([{ id: 1, code: 'A', created: null, url }], COLUMNS, 'UTC')

    expect(sheet.cells.D2).toEqual({ t: 's', v: url, l: { Target: url } })
  })

  it('writes a formatted number with its number format', () => {
    const sheet = buildWorksheet(
      [{ id: 1 }],
      [{ header: 'Price', value: () => ({ value: 12.5, format: '#,##0.00' }) }],
      'UTC',
    )

    expect(sheet.cells.A2).toEqual({ t: 'n', v: 12.5, z: '#,##0.00' })
  })

  it('sizes each column by its longest value within bounds', () => {
    const sheet = buildWorksheet(
      [{ id: 1, code: 'x'.repeat(100), created: '2026-11-12T09:30:00Z', url: null }],
      COLUMNS,
      'UTC',
    )

    expect(sheet.widths[0]).toBe(8)
    expect(sheet.widths[1]).toBe(60)
    expect(sheet.widths[2]).toBe(DATE_TIME_CELL_FORMAT.length + 2)
  })

  it('spans only the header row when there are no rows', () => {
    expect(buildWorksheet([], COLUMNS, 'UTC').ref).toBe('A1:D1')
  })
})

describe('toSheetName', () => {
  it('drops the characters Excel reserves and caps the length at 31', () => {
    expect(toSheetName('Parts [2026]/A')).toBe('Parts  2026  A')
    expect(toSheetName('x'.repeat(40))).toHaveLength(31)
    expect(toSheetName('  ')).toBe('Sheet1')
  })
})

describe('exportFilename', () => {
  it('dates the file by today and replaces characters a file system rejects', () => {
    expect(exportFilename('bought items', new Date('2026-11-12T12:00:00Z'))).toBe(
      'bought-items_2026-11-12.xlsx',
    )
    expect(exportFilename('a/b:c', new Date('2026-11-12T12:00:00Z'))).toBe('a-b-c_2026-11-12.xlsx')
  })
})
