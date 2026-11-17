import { describe, it, expect } from 'vitest'

import { autoMapColumns, buildRowsFromMapping, hasRequiredColumns, toDateString } from '../columnMapping'
import { makeProfile } from '../../__tests__/profileFactory'

import type { ImportFieldSpec } from '../../types/spreadsheetImport'

// A minimal, self-contained field set exercising all three `kind`s and a
// column name collision, deliberately not a real import (this module must
// stay import-free of @/features/*).
type TestField = 'project' | 'quantity' | 'partNumber' | 'articleName' | 'deliveryDate' | 'note'

const TEST_FIELDS: ImportFieldSpec<TestField>[] = [
  { key: 'project', alwaysRequired: true, kind: 'text', payloadKey: 'project_number' },
  { key: 'quantity', alwaysRequired: true, kind: 'number', payloadKey: 'quantity' },
  { key: 'partNumber', kind: 'text', payloadKey: 'part_number' },
  { key: 'articleName', kind: 'text', payloadKey: 'article_name' },
  { key: 'deliveryDate', kind: 'date', payloadKey: 'desired_delivery_date' },
  { key: 'note', kind: 'text', payloadKey: 'note' },
]

const PROFILE = makeProfile({
  project_number: ['Project', 'Job number'],
  quantity: ['Qty', 'Amount'],
  part_number: ['Part number', 'Item number'],
  article_name: ['Article name', 'Item name'],
  desired_delivery_date: ['Delivery date'],
  note: ['Note', 'Remark'],
})

interface TestRow {
  row_index: number
  project_number: string | null
  quantity: number | null
  part_number: string | null
  article_name: string | null
  desired_delivery_date: string | null
  note: string | null
}

const testSpec = {
  fields: TEST_FIELDS,
  buildRow: (values: Record<TestField, unknown>): TestRow => ({
    row_index: 0,
    project_number: values.project as string | null,
    quantity: values.quantity as number | null,
    part_number: values.partNumber as string | null,
    article_name: values.articleName as string | null,
    desired_delivery_date: values.deliveryDate as string | null,
    note: values.note as string | null,
  }),
}

describe('autoMapColumns', () => {
  it('maps a header to a field only when it is the single unused match', () => {
    const mapping = autoMapColumns(['Project', 'Part Number', 'Article Name', 'Qty'], TEST_FIELDS, PROFILE)

    expect(mapping.project).toBe('Project')
    expect(mapping.partNumber).toBe('Part Number')
    expect(mapping.articleName).toBe('Article Name')
    expect(mapping.quantity).toBe('Qty')
  })

  it('maps every configured column name, ignoring case and extra spaces', () => {
    const mapping = autoMapColumns(['  item   NAME ', 'Item Number'], TEST_FIELDS, PROFILE)

    expect(mapping.articleName).toBe('  item   NAME ')
    expect(mapping.partNumber).toBe('Item Number')
  })

  it('leaves a field null when two headers are candidates for it', () => {
    const mapping = autoMapColumns(['Note', 'Remark'], TEST_FIELDS, PROFILE)

    expect(mapping.note).toBeNull()
  })

  it('leaves a field null when no header matches', () => {
    const mapping = autoMapColumns(['Something Else'], TEST_FIELDS, PROFILE)

    expect(mapping.deliveryDate).toBeNull()
  })

  it('leaves a field null when the profile has no column names for it', () => {
    const mapping = autoMapColumns(['Note'], TEST_FIELDS, makeProfile({}))

    expect(mapping.note).toBeNull()
  })
})

describe('hasRequiredColumns', () => {
  it('needs a column for every always-required field', () => {
    expect(hasRequiredColumns({ project: 'P', quantity: 'Q' }, TEST_FIELDS)).toBe(true)
    expect(hasRequiredColumns({ project: 'P', quantity: null }, TEST_FIELDS)).toBe(false)
  })
})

describe('buildRowsFromMapping', () => {
  it('coerces each field by its kind and hands the result to buildRow', () => {
    const mapping = {
      project: 'Project',
      quantity: 'Qty',
      partNumber: 'Part Number',
      articleName: 'Article Name',
      deliveryDate: 'Delivery Date',
      note: 'Note',
    }
    const rawRows = [
      {
        Project: '  PRJ-001  ',
        Qty: '12,5',
        'Part Number': ' PN-1 ',
        'Article Name': 'Widget',
        'Delivery Date': '2026-09-01',
        Note: ' some note ',
      },
    ]

    const [row] = buildRowsFromMapping(rawRows, mapping, testSpec)

    expect(row).toEqual({
      row_index: 0,
      project_number: 'PRJ-001',
      quantity: 12.5,
      part_number: 'PN-1',
      article_name: 'Widget',
      desired_delivery_date: '2026-09-01',
      note: 'some note',
    })
  })

  it('leaves unmapped fields null', () => {
    const mapping = { project: 'Project', quantity: 'Qty' }
    const rawRows = [{ Project: 'PRJ-001', Qty: '3' }]

    const [row] = buildRowsFromMapping(rawRows, mapping, testSpec)

    expect(row?.part_number).toBeNull()
    expect(row?.article_name).toBeNull()
    expect(row?.desired_delivery_date).toBeNull()
    expect(row?.note).toBeNull()
  })
})

describe('toDateString', () => {
  it('reads a Date cell in the local calendar', () => {
    expect(toDateString(new Date(2026, 8, 1))).toBe('2026-09-01')
  })
})
