import { describe, it, expect } from 'vitest'

import { autoMapColumns, buildRowsFromMapping } from '@/shared/spreadsheet-import'
import { makeProfile } from '@/shared/spreadsheet-import/__tests__/profileFactory'
import { boughtItemsDemandImportAdapter as adapter } from '../boughtItemsDemandImportAdapter'
import type { BatchDemandRowInput, RowValidationResult, BoughtItemResponse } from '@/features/bought-items'



const PROFILE = makeProfile({
  project_number: ['Project'],
  quantity: ['Qty'],
  unit: ['Unit'],
  part_number: ['Part Number'],
  article_name: ['Article Name'],
  order_code: ['Order Code'],
  manufacturer_name: ['Manufacturer'],
  desired_delivery_date: ['Delivery Date'],
  note: ['Note'],
})

function makeRowInput(overrides: Partial<BatchDemandRowInput> = {}): BatchDemandRowInput {
  return {
    row_index: 0,
    project_number: 'PRJ-001',
    quantity: 1,
    unit: 'pcs',
    part_number: 'PN-1',
    article_name: 'Widget',
    order_code: null,
    manufacturer_name: null,
    desired_delivery_date: null,
    note: null,
    ...overrides,
  }
}

function makeBoughtItem(overrides: Partial<BoughtItemResponse> = {}): BoughtItemResponse {
  return {
    edit_version: 0,
    over_delivery_tolerance_percent: null,
    under_delivery_tolerance_percent: null,
    id: 1,
    public_id: 'aaaaaaaa-0000-0000-0000-000000000001',
    part_number: 'PN-1',
    status: 'active',
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    order_code_1: 'OC-1',
    order_code_2: null,
    gtin: null,
    ean: null,
    tariff_number: null,
    article_name: 'Catalogue Article Name',
    article_groups: [],
    data_source: 'WEB',
    mass: null,
    note: null,
    weblink: null,
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    manufacturer_id: 1,
    manufacturer_name: 'Acme',
    edp_part_id: null,
    edp_synced_at: null,
    pdf_files: [],
    pdm_file_id: null,
    pdm_file_version: null,
    pdm_locked_fields: [],
    pdm_sync_state: null,
    pdm_synced_at: null,
    product_family: null,
    product_family_id: null,
    revision: null,
    vault_id: null,
    ...overrides,
  }
}

function makeResult(overrides: Partial<RowValidationResult> = {}): RowValidationResult {
  return {
    row_index: 0,
    row_status: 'matched',
    match_source: 'part_number',
    matched_item: null,
    divergences: [],
    resolved_project_id: 1,
    errors: [],
    ...overrides,
  }
}

// autoMapColumns()/buildRowsFromMapping() themselves are covered generically
// in src/shared/spreadsheet-import/utils/__tests__/columnMapping.spec.ts: these
// exercise the bought-items field list/isMappingComplete key rule
// against the real adapter.
describe('boughtItemsDemandImportAdapter column mapping', () => {
  it('maps both Part Number and Article Name when both columns are present (regression)', () => {
    const headers = [
      'Project',
      'Part Number',
      'Article Name',
      'Qty',
      'Unit',
      'Order Code',
      'Manufacturer',
    ]
    const mapping = autoMapColumns(headers, adapter.fields, PROFILE)

    expect(mapping.partNumber).toBe('Part Number')
    expect(mapping.articleName).toBe('Article Name')
    expect(adapter.isMappingComplete(mapping)).toBe(true)
  })

  // The column names come from the import profile by each field's payload
  // key, so a profile naming every payload key maps every field.
  it('reads the column names of every field from the profile by payload key', () => {
    const profile = makeProfile(
      Object.fromEntries(adapter.fields.map((f) => [f.payloadKey, [`Column ${f.payloadKey}`]])),
    )

    const mapping = autoMapColumns(
      adapter.fields.map((f) => `Column ${f.payloadKey}`),
      adapter.fields,
      profile,
    )

    for (const field of adapter.fields) {
      expect(mapping[field.key]).toBe(`Column ${field.payloadKey}`)
    }
  })

  it('reads the bought_item_demand profile', () => {
    expect(adapter.importType).toBe('bought_item_demand')
  })

  it('is complete with only Project, Qty, Unit, Part Number mapped', () => {
    const mapping = autoMapColumns(['Project', 'Qty', 'Unit', 'Part Number'], adapter.fields, PROFILE)

    expect(adapter.isMappingComplete(mapping)).toBe(true)
  })

  it('is not complete with Order Code mapped but no Manufacturer', () => {
    const mapping = autoMapColumns(['Project', 'Qty', 'Unit', 'Order Code'], adapter.fields, PROFILE)

    expect(mapping.orderCode).toBe('Order Code')
    expect(mapping.manufacturerName).toBeNull()
    expect(adapter.isMappingComplete(mapping)).toBe(false)
  })

  it('is complete with Order Code and Manufacturer both mapped', () => {
    const mapping = autoMapColumns(
      ['Project', 'Qty', 'Unit', 'Order Code', 'Manufacturer'],
      adapter.fields,
      PROFILE,
    )

    expect(adapter.isMappingComplete(mapping)).toBe(true)
  })

  it('is not complete when neither part number nor order code + manufacturer is mapped', () => {
    const mapping = autoMapColumns(['Project', 'Qty', 'Unit'], adapter.fields, PROFILE)

    expect(adapter.isMappingComplete(mapping)).toBe(false)
  })

  it('buildRowsFromMapping produces the BatchDemandRowInput shape with trimming/number/date normalization', () => {
    const mapping = {
      project: 'Project',
      quantity: 'Qty',
      unit: 'Unit',
      partNumber: 'Part Number',
      articleName: 'Article Name',
      orderCode: 'Order Code',
      manufacturerName: 'Manufacturer',
      desiredDeliveryDate: 'Delivery Date',
      note: 'Note',
    }
    const rawRows = [
      {
        Project: '  PRJ-001  ',
        Qty: '12,5',
        Unit: 'pcs',
        'Part Number': ' PN-1 ',
        'Article Name': 'Widget',
        'Order Code': 'OC-1',
        Manufacturer: 'ACME',
        'Delivery Date': '2026-09-01',
        Note: ' some note ',
      },
    ]

    const [row] = buildRowsFromMapping(rawRows, mapping, adapter)

    expect(row).toEqual({
      row_index: 0,
      project_number: 'PRJ-001',
      quantity: 12.5,
      unit: 'pcs',
      part_number: 'PN-1',
      article_name: 'Widget',
      order_code: 'OC-1',
      manufacturer_name: 'ACME',
      desired_delivery_date: '2026-09-01',
      note: 'some note',
    })
  })
})

describe('boughtItemsDemandImportAdapter.isRowComplete', () => {
  it('is true with a part number and no order code/manufacturer', () => {
    expect(adapter.isRowComplete(makeRowInput())).toBe(true)
  })

  it('is true with order code + manufacturer and no part number', () => {
    expect(
      adapter.isRowComplete(
        makeRowInput({ part_number: null, order_code: 'OC-1', manufacturer_name: 'Acme' }),
      ),
    ).toBe(true)
  })

  it('is false without any lookup key', () => {
    expect(adapter.isRowComplete(makeRowInput({ part_number: null }))).toBe(false)
  })

  it('is false without a project, quantity, or unit', () => {
    expect(adapter.isRowComplete(makeRowInput({ project_number: null }))).toBe(false)
    expect(adapter.isRowComplete(makeRowInput({ quantity: null }))).toBe(false)
    expect(adapter.isRowComplete(makeRowInput({ unit: '' }))).toBe(false)
  })
})

describe('boughtItemsDemandImportAdapter.reviewColumns', () => {
  const [partNumberColumn, itemColumn, manufacturerColumn] = adapter.reviewColumns

  it('Part Number column shows the catalogue part number only when matched via order code + manufacturer', () => {
    const row = makeRowInput({ part_number: null })
    const matchedResult = makeResult({
      match_source: 'order_code_manufacturer',
      matched_item: makeBoughtItem({ part_number: 'PN-CATALOGUE' }),
    })

    expect(partNumberColumn!.secondary!(row, matchedResult)).toBe('PN-CATALOGUE')
    expect(
      partNumberColumn!.secondary!(row, makeResult({ match_source: 'part_number' })),
    ).toBeNull()
  })

  it('Item column combines article name and order code, and shows the catalogue name only when it diverges', () => {
    const row = makeRowInput({ article_name: 'File Name', order_code: 'OC-1' })

    expect(itemColumn!.primary(row)).toBe('File Name\nOC-1')
    expect(
      itemColumn!.secondary!(
        row,
        makeResult({
          divergences: [{ field: 'article_name', db_value: 'DB Name', file_value: 'File Name' }],
          matched_item: makeBoughtItem({ article_name: 'DB Name' }),
        }),
      ),
    ).toBe('DB Name')
    expect(itemColumn!.secondary!(row, makeResult({ divergences: [] }))).toBeNull()
  })

  it('Manufacturer column shows the row manufacturer name', () => {
    expect(manufacturerColumn!.primary(makeRowInput({ manufacturer_name: 'Acme' }))).toBe('Acme')
  })
})

describe('boughtItemsDemandImportAdapter.blockedHintKey', () => {
  it('returns the matching hint key for each blocked status, and null otherwise', () => {
    expect(adapter.blockedHintKey('not_found', undefined)).toBe(
      'boughtItems.demands.batchCreate.errors.itemNotFound',
    )
    expect(adapter.blockedHintKey('ambiguous', undefined)).toBe(
      'boughtItems.demands.batchCreate.errors.ambiguous',
    )
    expect(adapter.blockedHintKey('unresolved_reference', undefined)).toBe(
      'boughtItems.demands.batchCreate.errors.projectNotFound',
    )
    expect(adapter.blockedHintKey('invalid', undefined)).toBeNull()
    expect(adapter.blockedHintKey('matched', undefined)).toBeNull()
  })
})

describe('boughtItemsDemandImportAdapter.quantityUnit', () => {
  it('formats the row unit via formatUnit', () => {
    expect(adapter.quantityUnit!(makeRowInput({ unit: 'PCS' }))).toBeTruthy()
  })
})
