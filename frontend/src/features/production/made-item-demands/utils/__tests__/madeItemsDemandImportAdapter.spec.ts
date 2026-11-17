import { describe, it, expect } from 'vitest'

import { autoMapColumns, buildRowsFromMapping } from '@/shared/spreadsheet-import'
import { makeProfile } from '@/shared/spreadsheet-import/__tests__/profileFactory'
import { madeItemsDemandImportAdapter as adapter } from '../madeItemsDemandImportAdapter'
import { BATCH_MADE_ITEM_DEMAND_IMPORT_DRAFT_STORAGE_KEY } from '@/core/stores/resetOnLogout'
import type {
  MadeItemBatchDemandRowInput,
  MadeItemRowValidationResult,
  MadeItemResponse,
} from '@/features/made-items'



const PROFILE = makeProfile({
  project_number: ['Project'],
  quantity: ['Qty'],
  part_number: ['Part Number'],
  revision: ['Revision'],
  article_name: ['Article Name'],
  desired_delivery_date: ['Delivery Date'],
  note: ['Note'],
})

function makeRowInput(overrides: Partial<MadeItemBatchDemandRowInput> = {}): MadeItemBatchDemandRowInput {
  return {
    row_index: 0,
    project_number: 'PRJ-001',
    quantity: 1,
    part_number: 'PN-1',
    revision: 'A',
    article_name: 'Bracket',
    desired_delivery_date: null,
    note: null,
    ...overrides,
  }
}

function makeMadeItem(overrides: Partial<MadeItemResponse> = {}): MadeItemResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: '33333333-3333-3333-3333-333333333333',
    part_number: 'PN-1',
    status: 'active',
    archived: false,
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    revision: 'A',
    revision_date: null,
    revision_note: null,
    article_name: 'Catalogue Bracket',
    article_groups: [],
    data_source: 'WEB',
    material: null,
    mass: null,
    base_size: null,
    note: null,
    weblink: null,
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    changed_by_id: null,
    changed_by: null,
    bought_item_id: null,
    bought_item: null,
    source_item_id: null,
    customer_id: null,
    customer_name: null,
    customer_part_number: null,
    customer_revision: null,
    source_item: null,
    source_label: '',
    source_sublabel: '',
    processes: [],
    pdm_file_id: null,
    pdm_file_version: null,
    pdm_locked_fields: [],
    pdm_source_item_id: null,
    pdm_sync_state: null,
    pdm_synced_at: null,
    vault_id: null,
    ...overrides,
  }
}

function makeResult(overrides: Partial<MadeItemRowValidationResult> = {}): MadeItemRowValidationResult {
  return {
    row_index: 0,
    row_status: 'matched',
    match_source: 'part_number_revision',
    matched_item: null,
    divergences: [],
    resolved_project_id: 1,
    errors: [],
    ...overrides,
  }
}

// autoMapColumns()/buildRowsFromMapping() themselves are covered generically
// in src/shared/spreadsheet-import/utils/__tests__/columnMapping.spec.ts: these
// exercise the made-items field list/isMappingComplete key rule
// against the real adapter.
describe('madeItemsDemandImportAdapter column mapping', () => {
  it('lists fields in the plan order with the right payload keys', () => {
    expect(adapter.fields.map((f) => f.key)).toEqual([
      'project',
      'quantity',
      'partNumber',
      'revision',
      'articleName',
      'desiredDeliveryDate',
      'note',
    ])
    expect(adapter.fields.map((f) => f.payloadKey)).toEqual([
      'project_number',
      'quantity',
      'part_number',
      'revision',
      'article_name',
      'desired_delivery_date',
      'note',
    ])
  })

  it('marks project, quantity, partNumber and revision as alwaysRequired, and nothing else', () => {
    const required = adapter.fields.filter((f) => f.alwaysRequired).map((f) => f.key)
    expect(required).toEqual(['project', 'quantity', 'partNumber', 'revision'])
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

  it('reads the made_item_demand profile', () => {
    expect(adapter.importType).toBe('made_item_demand')
  })

  it('is complete with Project, Qty, Part Number and Revision mapped', () => {
    const mapping = autoMapColumns(['Project', 'Qty', 'Part Number', 'Revision'], adapter.fields, PROFILE)

    expect(adapter.isMappingComplete(mapping)).toBe(true)
  })

  it('is not complete without Revision mapped, even with Part Number mapped', () => {
    const mapping = autoMapColumns(['Project', 'Qty', 'Part Number'], adapter.fields, PROFILE)

    expect(mapping.partNumber).toBe('Part Number')
    expect(mapping.revision).toBeNull()
    expect(adapter.isMappingComplete(mapping)).toBe(false)
  })

  it('is not complete without Part Number mapped, even with Revision mapped', () => {
    const mapping = autoMapColumns(['Project', 'Qty', 'Revision'], adapter.fields, PROFILE)

    expect(adapter.isMappingComplete(mapping)).toBe(false)
  })

  it('buildRowsFromMapping produces the MadeItemBatchDemandRowInput shape with trimming/number/date normalization', () => {
    const mapping = {
      project: 'Project',
      quantity: 'Qty',
      partNumber: 'Part Number',
      revision: 'Revision',
      articleName: 'Article Name',
      desiredDeliveryDate: 'Delivery Date',
      note: 'Note',
    }
    const rawRows = [
      {
        Project: '  PRJ-001  ',
        Qty: '12,5',
        'Part Number': ' PN-1 ',
        Revision: ' A ',
        'Article Name': 'Bracket',
        'Delivery Date': '2026-09-01',
        Note: ' some note ',
      },
    ]

    const [row] = buildRowsFromMapping(rawRows, mapping, adapter)

    expect(row).toEqual({
      row_index: 0,
      project_number: 'PRJ-001',
      quantity: 12.5,
      part_number: 'PN-1',
      revision: 'A',
      article_name: 'Bracket',
      desired_delivery_date: '2026-09-01',
      note: 'some note',
    })
  })
})

describe('madeItemsDemandImportAdapter.isRowComplete', () => {
  it('is true with project, quantity, part number and revision', () => {
    expect(adapter.isRowComplete(makeRowInput())).toBe(true)
  })

  it('is false without a revision (part number alone is not enough)', () => {
    expect(adapter.isRowComplete(makeRowInput({ revision: null }))).toBe(false)
  })

  it('is false without a part number', () => {
    expect(adapter.isRowComplete(makeRowInput({ part_number: null }))).toBe(false)
  })

  it('is false without a project or a positive quantity', () => {
    expect(adapter.isRowComplete(makeRowInput({ project_number: null }))).toBe(false)
    expect(adapter.isRowComplete(makeRowInput({ quantity: null }))).toBe(false)
    expect(adapter.isRowComplete(makeRowInput({ quantity: 0 }))).toBe(false)
  })
})

describe('madeItemsDemandImportAdapter.buildRow', () => {
  it('builds a row with row_index 0 as a placeholder (the draft store assigns the real one)', () => {
    const row = adapter.buildRow({
      project: 'PRJ-001',
      quantity: 3,
      partNumber: 'PN-1',
      revision: 'A',
      articleName: null,
      desiredDeliveryDate: null,
      note: null,
    })

    expect(row).toEqual({
      row_index: 0,
      project_number: 'PRJ-001',
      quantity: 3,
      part_number: 'PN-1',
      revision: 'A',
      article_name: null,
      desired_delivery_date: null,
      note: null,
    })
  })
})

describe('madeItemsDemandImportAdapter.reviewColumns', () => {
  const [partNumberColumn, itemColumn] = adapter.reviewColumns

  it('Part Number column stacks part number and revision on two lines, and has no secondary', () => {
    const row = makeRowInput({ part_number: 'PN-1', revision: 'A' })

    expect(partNumberColumn!.primary(row)).toBe('PN-1\nRev A')
    expect(partNumberColumn!.secondary).toBeUndefined()
  })

  it('Part Number column falls back to null when part number is missing', () => {
    expect(partNumberColumn!.primary(makeRowInput({ part_number: null }))).toBeNull()
  })

  it('Item column shows the file article name, and the catalogue name only when it diverges', () => {
    const row = makeRowInput({ article_name: 'File Name' })

    expect(itemColumn!.primary(row)).toBe('File Name')
    expect(
      itemColumn!.secondary!(
        row,
        makeResult({
          divergences: [{ field: 'article_name', db_value: 'DB Name', file_value: 'File Name' }],
          matched_item: makeMadeItem({ article_name: 'DB Name' }),
        }),
      ),
    ).toBe('DB Name')
    expect(itemColumn!.secondary!(row, makeResult({ divergences: [] }))).toBeNull()
  })

  it('Item column secondary ignores a status-only divergence', () => {
    const row = makeRowInput()
    const result = makeResult({
      divergences: [{ field: 'status', db_value: 'inactive', file_value: null }],
      matched_item: makeMadeItem({ status: 'inactive' }),
    })

    expect(itemColumn!.secondary!(row, result)).toBeNull()
  })
})

describe('madeItemsDemandImportAdapter.blockedHintKey', () => {
  it('returns the matching hint key for each blocked status, and null otherwise (including invalid)', () => {
    expect(adapter.blockedHintKey('not_found', undefined)).toBe(
      'madeItems.demands.batchCreate.errors.itemNotFound',
    )
    expect(adapter.blockedHintKey('ambiguous', undefined)).toBe(
      'madeItems.demands.batchCreate.errors.ambiguous',
    )
    expect(adapter.blockedHintKey('unresolved_reference', undefined)).toBe(
      'madeItems.demands.batchCreate.errors.projectNotFound',
    )
    expect(adapter.blockedHintKey('invalid', undefined)).toBeNull()
    expect(adapter.blockedHintKey('matched', undefined)).toBeNull()
  })
})

describe('madeItemsDemandImportAdapter.divergenceLabel', () => {
  it('translates article_name and status via the divergenceField i18n keys', () => {
    const t = (key: string) => key
    expect(adapter.divergenceLabel('article_name', t)).toBe(
      'madeItems.demands.batchCreate.divergenceField.article_name',
    )
    expect(adapter.divergenceLabel('status', t)).toBe(
      'madeItems.demands.batchCreate.divergenceField.status',
    )
  })
})

describe('madeItemsDemandImportAdapter.divergenceValue', () => {
  it('translates a status value via the catalogue status i18n keys and passes other values through', () => {
    const t = (key: string) => key
    expect(adapter.divergenceValue?.('status', 'replaced', t)).toBe('madeItems.catalogue.status.replaced')
    expect(adapter.divergenceValue?.('status', 'inactive', t)).toBe('madeItems.catalogue.status.inactive')
    expect(adapter.divergenceValue?.('article_name', 'Bracket', t)).toBe('Bracket')
  })
})

describe('madeItemsDemandImportAdapter thumbnail wiring', () => {
  it('reads id/article_name off the matched item', () => {
    const item = makeMadeItem({ id: 42, article_name: 'Widget' })

    expect(adapter.thumbnail!.itemId(item)).toBe(42)
    expect(adapter.thumbnail!.itemName(item)).toBe('Widget')
  })
})

describe('madeItemsDemandImportAdapter identity', () => {
  it('uses the made-items id, i18n prefix and the registered storage key, and has no quantityUnit', () => {
    expect(adapter.id).toBe('made-items')
    expect(adapter.i18nPrefix).toBe('madeItems.demands.batchCreate')
    expect(adapter.storageKey).toBe(BATCH_MADE_ITEM_DEMAND_IMPORT_DRAFT_STORAGE_KEY)
    expect(adapter.quantityUnit).toBeUndefined()
  })
})
