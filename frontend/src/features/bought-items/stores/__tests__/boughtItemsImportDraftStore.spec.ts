import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { ReadSpreadsheetResult } from '@/shared/spreadsheet-import'
import type { BoughtItemImportField } from '../../utils/boughtItemsImportFields'
import type {
  BoughtItemImportResult,
  BoughtItemImportRow,
  CommitBoughtItemImportResponse,
  ValidateBoughtItemImportResponse,
} from '../../types/boughtItemsImportTypes'

const readSpreadsheetMock =
  vi.fn<(file: File) => Promise<ReadSpreadsheetResult<BoughtItemImportField>>>()
vi.mock('@/shared/spreadsheet-import', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/shared/spreadsheet-import')>()),
  readSpreadsheet: (file: File) => readSpreadsheetMock(file),
}))

const validateMock =
  vi.fn<
    (rows: BoughtItemImportRow[], lookup: boolean) => Promise<ValidateBoughtItemImportResponse>
  >()
const commitMock =
  vi.fn<(rows: BoughtItemImportRow[], lookup: boolean) => Promise<CommitBoughtItemImportResponse>>()
vi.mock('../../api/boughtItemsImportApi', () => ({
  validateBoughtItemImport: (rows: BoughtItemImportRow[], lookup: boolean) =>
    validateMock(rows, lookup),
  commitBoughtItemImport: (rows: BoughtItemImportRow[], lookup: boolean) =>
    commitMock(rows, lookup),
}))

import { useBoughtItemsImportDraftStore } from '../boughtItemsImportDraftStore'

const FILE = new File([''], 'items.xlsx')

function sheet(mapping: ReadSpreadsheetResult<BoughtItemImportField>['mapping']) {
  return {
    headers: ['Name', 'Code', 'Maker'],
    rows: [
      { Name: 'Cylinder', Code: 'C-1', Maker: 'Festo' },
      { Name: 'Valve', Code: 'V-1', Maker: 'Festo' },
    ],
    headerRow: 1,
    mapping,
  }
}

const FULL_MAPPING = { articleName: 'Name', orderCode1: 'Code', manufacturerName: 'Maker' }

function result(rowIndex: number, status: BoughtItemImportResult['row_status']) {
  return { row_index: rowIndex, row_status: status } as BoughtItemImportResult
}

describe('useBoughtItemsImportDraftStore', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('opens the review when the profile mapped every required column', async () => {
    readSpreadsheetMock.mockResolvedValue(sheet(FULL_MAPPING))
    const store = useBoughtItemsImportDraftStore()

    await store.loadFile(FILE)

    expect(store.step).toBe('review')
    expect(store.rows.map((r) => r.data.order_code_1)).toEqual(['C-1', 'V-1'])
    expect(store.rows[0]?.data.manufacturer_name).toBe('Festo')
  })

  it('asks for the mapping when a required column was not recognised', async () => {
    readSpreadsheetMock.mockResolvedValue(sheet({ articleName: 'Name', orderCode1: 'Code' }))
    const store = useBoughtItemsImportDraftStore()

    await store.loadFile(FILE)

    expect(store.step).toBe('mapColumns')
    store.confirmMapping(FULL_MAPPING)
    expect(store.step).toBe('review')
    expect(store.rows).toHaveLength(2)
  })

  it('counts the ready rows of a fresh validation only', async () => {
    readSpreadsheetMock.mockResolvedValue(sheet(FULL_MAPPING))
    validateMock.mockResolvedValue({
      results: [result(0, 'ready'), result(1, 'exists')],
      ready_count: 1,
    })
    const store = useBoughtItemsImportDraftStore()
    await store.loadFile(FILE)

    await store.validate()
    expect(store.readyCount).toBe(1)
    expect(validateMock.mock.calls[0]?.[0].map((r) => r.row_index)).toEqual([0, 1])

    store.updateRow(store.rows[1]!.clientId, { ...store.rows[1]!.data, article_name: 'Valve 2' })
    expect(store.readyCount).toBe(0)
  })

  it('drops the created rows after a commit and keeps the rest', async () => {
    readSpreadsheetMock.mockResolvedValue(sheet(FULL_MAPPING))
    commitMock.mockResolvedValue({
      created_item_ids: [7],
      created_row_indexes: [0],
      handled_row_indexes: [0],
      linked_item_ids: [],
    })
    const store = useBoughtItemsImportDraftStore()
    await store.loadFile(FILE)

    const created = await store.commit()

    expect(created).toBe(1)
    expect(store.rows.map((r) => r.data.order_code_1)).toEqual(['V-1'])
    expect(store.step).toBe('review')
  })

  it('discards the draft once the commit created every row', async () => {
    readSpreadsheetMock.mockResolvedValue(sheet(FULL_MAPPING))
    commitMock.mockResolvedValue({
      created_item_ids: [7, 8],
      created_row_indexes: [0, 1],
      handled_row_indexes: [0, 1],
      linked_item_ids: [],
    })
    const store = useBoughtItemsImportDraftStore()
    await store.loadFile(FILE)

    await store.commit()

    expect(store.step).toBe('upload')
    expect(store.hasDraft).toBe(false)
  })

  it('accepts an order code alone with the lookup and sends the flag', async () => {
    readSpreadsheetMock.mockResolvedValue(sheet({ orderCode1: 'Code' }))
    validateMock.mockResolvedValue({ results: [], ready_count: 0 })
    const store = useBoughtItemsImportDraftStore()
    store.lookup = true

    await store.loadFile(FILE)
    await store.validate()

    expect(store.step).toBe('review')
    expect(validateMock.mock.calls[0]?.[1]).toBe(true)
  })

  it('pins a candidate and skips the lookup per row', async () => {
    readSpreadsheetMock.mockResolvedValue(sheet(FULL_MAPPING))
    const store = useBoughtItemsImportDraftStore()
    await store.loadFile(FILE)
    const [first, second] = store.rows

    store.pinPart(first!.clientId, 42)
    store.skipLookup(second!.clientId)

    expect(store.rows[0]?.data).toMatchObject({ edp_part_id: 42, skip_lookup: false })
    expect(store.rows[1]?.data).toMatchObject({ edp_part_id: null, skip_lookup: true })
  })
})
