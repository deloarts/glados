import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { makeMadeItemResponse } from '@/test-utils/factories'
import { MADE_ITEMS_CATALOGUE_COLUMNS } from '../../stores/madeItemsCatalogueColumnsStore'
import { madeItemsExportColumns } from '../madeItemsCatalogueExport'

import type { MadeItemColumnDefinition } from '../../stores/madeItemsCatalogueColumnsStore'
import type { MadeItemProcessResponse, MadeItemResponse } from '../../types/madeItemsResponse'

const t = (key: string): string => i18n.global.t(key)

function columnsFor(fields: MadeItemColumnDefinition['field'][]): MadeItemColumnDefinition[] {
  return fields.map((field) => {
    const column = MADE_ITEMS_CATALOGUE_COLUMNS.find((c) => c.field === field)!
    return { ...column, header: t(column.headerKey), phoneClass: undefined }
  })
}

function exportedRow(fields: MadeItemColumnDefinition['field'][], item: MadeItemResponse) {
  const columns = madeItemsExportColumns(columnsFor(fields), t, 'enGB')
  return Object.fromEntries(columns.map((column) => [column.header, column.value(item)]))
}

function makeProcess(id: number, groupIndex: number, name: string): MadeItemProcessResponse {
  return {
    id,
    public_id: `00000000-0000-0000-0000-${String(id).padStart(12, '0')}`,
    created: '2026-07-01',
    note: null,
    estimated_setup_minutes: null,
    estimated_minutes_per_piece: null,
    creator_id: 1,
    fabrication_method_id: id,
    role: 'fabrication' as const,
    inspection_method_id: null,
    inspection_method_name: null,
    fabrication_method_name: { enGB: name },
    made_item_id: 1,
    position: id,
    group_index: groupIndex,
  }
}

describe('madeItemsExportColumns', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('leaves out the picture and files columns and ends with the link to the item', () => {
    const columns = madeItemsExportColumns(columnsFor(['id', 'image', 'part_number', 'files']), t, 'enGB')

    expect(columns.map((column) => column.header)).toEqual([
      t('madeItems.catalogue.columns.id'),
      t('madeItems.catalogue.columns.partNumber'),
      'Link',
    ])
    expect(columns[2]!.value(makeMadeItemResponse({ public_id: 'mi-7' }))).toEqual({
      text: `${window.location.origin}/resolve/mi-7`,
      url: `${window.location.origin}/resolve/mi-7`,
    })
  })

  it('writes the routing as text and the source as its label and sublabel', () => {
    const row = exportedRow(
      ['processes', 'source_label'],
      makeMadeItemResponse({
        processes: [makeProcess(1, 0, 'Sawing'), makeProcess(2, 1, 'Milling')],
        source_label: 'Round bar',
        source_sublabel: '1.0037 Ø20',
      }),
    )

    expect(row[t('madeItems.catalogue.columns.processes')]).toBe('Sawing → Milling')
    expect(row[t('madeItems.catalogue.columns.source')]).toBe('Round bar, 1.0037 Ø20')
  })

  it('writes the revision date as a calendar date and the status as its label', () => {
    const row = exportedRow(
      ['revision_date', 'status', 'mass'],
      makeMadeItemResponse({ revision_date: '2026-05-04', status: 'active', mass: 10 }),
    )

    expect(row[t('madeItems.catalogue.columns.revisionDate')]).toEqual({ iso: '2026-05-04' })
    expect(row[t('madeItems.catalogue.columns.status')]).toBe(t('madeItems.catalogue.status.active'))
    expect(row[t('madeItems.catalogue.columns.mass')]).toBe(10)
  })

  it('leaves an empty routing and a missing revision date empty', () => {
    const row = exportedRow(['processes', 'revision_date'], makeMadeItemResponse({ processes: [] }))

    expect(row[t('madeItems.catalogue.columns.processes')]).toBeNull()
    expect(row[t('madeItems.catalogue.columns.revisionDate')]).toBeNull()
  })
})
