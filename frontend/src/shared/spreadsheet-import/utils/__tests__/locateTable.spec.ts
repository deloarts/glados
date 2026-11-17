import { describe, it, expect } from 'vitest'

import { locateTable } from '../locateTable'
import { makeProfile } from '../../__tests__/profileFactory'
import { SpreadsheetImportError } from '../../types/spreadsheetImport'

import type { ImportFieldSpec } from '../../types/spreadsheetImport'

type Field = 'project' | 'quantity' | 'note'

const FIELDS: ImportFieldSpec<Field>[] = [
  { key: 'project', alwaysRequired: true, kind: 'text', payloadKey: 'project_number' },
  { key: 'quantity', alwaysRequired: true, kind: 'number', payloadKey: 'quantity' },
  { key: 'note', kind: 'text', payloadKey: 'note' },
]

const NAMES = {
  project_number: ['Project'],
  quantity: ['Qty'],
  note: ['Note'],
}

function thrown(fn: () => unknown): SpreadsheetImportError {
  try {
    fn()
  } catch (e) {
    if (e instanceof SpreadsheetImportError) return e
    throw e
  }
  throw new Error('expected a SpreadsheetImportError')
}

describe('locateTable', () => {
  it('reads the first row as the header when it names the fields', () => {
    const table = locateTable(
      [
        ['Project', 'Qty'],
        ['P-1', 2],
      ],
      makeProfile(NAMES),
      FIELDS,
    )

    expect(table.headerRow).toBe(1)
    expect(table.headers).toEqual(['Project', 'Qty'])
    expect(table.rows).toEqual([{ Project: 'P-1', Qty: 2 }])
  })

  it('detects a header below a title block', () => {
    const table = locateTable(
      [
        ['Order list, note: prices excl. VAT'],
        [null, null],
        ['Customer', 'ACME'],
        ['Project', 'Qty', 'Note'],
        ['P-1', 2, 'urgent'],
      ],
      makeProfile(NAMES),
      FIELDS,
    )

    expect(table.headerRow).toBe(4)
    expect(table.rows).toEqual([{ Project: 'P-1', Qty: 2, Note: 'urgent' }])
  })

  it('takes the row naming the most fields over an earlier one naming fewer', () => {
    const table = locateTable(
      [
        ['Note', 'see below'],
        ['Project', 'Qty', 'Note'],
        ['P-1', 1, null],
      ],
      makeProfile(NAMES),
      FIELDS,
    )

    expect(table.headerRow).toBe(2)
  })

  it('uses a fixed header row and data offset from the profile', () => {
    const table = locateTable(
      [
        ['Project', 'Qty'],
        ['Projekt', 'Menge'],
        ['units', 'pcs'],
        ['P-1', 3],
      ],
      makeProfile(NAMES, { header_row: 1, data_offset: 3 }),
      FIELDS,
    )

    expect(table.headerRow).toBe(1)
    expect(table.rows).toEqual([{ Project: 'P-1', Qty: 3 }])
  })

  it('skips empty rows wherever they are and keeps the rows after a gap', () => {
    const table = locateTable(
      [['Project', 'Qty'], ['P-1', 1], [null, ''], [], ['P-2', 2]],
      makeProfile(NAMES),
      FIELDS,
    )

    expect(table.rows.map((r) => r.Project)).toEqual(['P-1', 'P-2'])
  })

  it('drops columns without a header and numbers repeated headers', () => {
    const table = locateTable(
      [
        ['Project', null, 'Qty', 'Qty'],
        ['P-1', 'stray', 1, 2],
      ],
      makeProfile(NAMES),
      FIELDS,
    )

    expect(table.headers).toEqual(['Project', 'Qty', 'Qty (2)'])
    expect(table.rows).toEqual([{ Project: 'P-1', Qty: 1, 'Qty (2)': 2 }])
  })

  it('refuses a sheet where no row names any field and lists the required ones', () => {
    const error = thrown(() =>
      locateTable(
        [
          ['A', 'B'],
          [1, 2],
        ],
        makeProfile(NAMES),
        FIELDS,
      ),
    )

    expect(error.code).toBe('headerNotFound')
    expect(error.missing).toEqual(['project_number', 'quantity'])
  })

  it('refuses more data rows than the profile allows', () => {
    const error = thrown(() =>
      locateTable(
        [['Project', 'Qty'], ['P-1', 1], ['P-2', 2], ['P-3', 3]],
        makeProfile(NAMES, { max_rows: 2 }),
        FIELDS,
      ),
    )

    expect(error.code).toBe('tooManyRows')
    expect(error.limit).toBe(2)
    expect(error.count).toBe(3)
  })

  it('refuses an empty sheet and a sheet with a header only', () => {
    expect(thrown(() => locateTable([], makeProfile(NAMES), FIELDS)).code).toBe('emptyFile')
    expect(thrown(() => locateTable([['Project', 'Qty']], makeProfile(NAMES), FIELDS)).code).toBe(
      'emptyFile',
    )
  })
})
