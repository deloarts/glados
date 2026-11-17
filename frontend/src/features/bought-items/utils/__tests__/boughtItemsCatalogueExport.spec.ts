import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { makeBoughtItemResponse } from '@/test-utils/factories'
import { BOUGHT_ITEMS_CATALOGUE_COLUMNS } from '../../stores/boughtItemsCatalogueColumnsStore'
import { boughtItemsExportColumns } from '../boughtItemsCatalogueExport'

import type { BoughtItemColumnDefinition } from '../../stores/boughtItemsCatalogueColumnsStore'
import type { BoughtItemResponse } from '../../types/boughtItemsResponse'

const t = (key: string): string => i18n.global.t(key)

function columnsFor(fields: BoughtItemColumnDefinition['field'][]): BoughtItemColumnDefinition[] {
  return fields.map((field) => {
    const column = BOUGHT_ITEMS_CATALOGUE_COLUMNS.find((c) => c.field === field)!
    return { ...column, header: t(column.headerKey), phoneClass: undefined }
  })
}

function exportedRow(fields: BoughtItemColumnDefinition['field'][], item: BoughtItemResponse) {
  const columns = boughtItemsExportColumns(columnsFor(fields), t)
  return Object.fromEntries(columns.map((column) => [column.header, column.value(item)]))
}

type ArticleGroup = BoughtItemResponse['article_groups'][number]

function makeArticleGroup(id: number, name: string): ArticleGroup {
  return {
    id,
    name: { enGB: name },
    description: {},
    label_color: '#6366f1',
    label_font_color: '#ffffff',
    archived: false,
    created: '2026-01-01T00:00:00Z',
    changed: '2026-01-01T00:00:00Z',
    creator_id: 1,
    creator: null,
    changed_by_id: null,
    changed_by: null,
    public_id: `00000000-0000-0000-0000-00000000000${id}`,
  }
}

describe('boughtItemsExportColumns', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('follows the visible columns and ends with the lasting link to the item', () => {
    const columns = boughtItemsExportColumns(columnsFor(['part_number', 'id', 'article_name']), t)

    expect(columns.map((column) => column.header)).toEqual(['Part Number', 'ID', 'Article Name', 'Link'])
    const link = columns[3]!.value(makeBoughtItemResponse({ public_id: 'abc-123' }))
    expect(link).toEqual({
      text: `${window.location.origin}/resolve/abc-123`,
      url: `${window.location.origin}/resolve/abc-123`,
    })
  })

  it('writes status and data source as their labels and flags an archived item', () => {
    const row = exportedRow(
      ['status', 'data_source'],
      makeBoughtItemResponse({ status: 'replaced', archived: true, data_source: 'CAD' }),
    )

    expect(row[t('boughtItems.catalogue.columns.status')]).toBe(`${t('boughtItems.catalogue.status.replaced')}, ${t('common.archivedTag')}`)
    expect(row[t('boughtItems.catalogue.columns.dataSource')]).toBe(t('boughtItems.catalogue.dataSources.CAD'))
  })

  it('keeps codes as text, numbers as numbers and lists the labels by name', () => {
    const row = exportedRow(
      ['gtin', 'mass', 'article_groups', 'pdf_files'],
      makeBoughtItemResponse({
        gtin: '04012345678901',
        mass: 12.5,
        article_groups: [makeArticleGroup(1, 'Fasteners'), makeArticleGroup(2, 'Steel')],
        pdf_files: [
          { id: 1, file_name: 'a.pdf', mime_type: 'application/pdf' },
          { id: 2, file_name: 'b.pdf', mime_type: 'application/pdf' },
        ],
      }),
    )

    expect(row[t('boughtItems.catalogue.columns.gtin')]).toBe('04012345678901')
    expect(row[t('boughtItems.catalogue.columns.mass')]).toBe(12.5)
    expect(row[t('boughtItems.catalogue.columns.groups')]).toBe('Fasteners, Steel')
    expect(row[t('boughtItems.catalogue.columns.files')]).toBe(2)
  })

  it('writes the dates as dates followed by the person who set them', () => {
    const columns = boughtItemsExportColumns(columnsFor(['created', 'changed']), t)
    const item = makeBoughtItemResponse({
      created: '2026-03-01T08:00:00Z',
      creator: { id: 4, full_name: 'Ada Lovelace', username: 'ada', has_avatar: false, public_id: 'u-4' },
      changed: '2026-04-01T08:00:00Z',
      changed_by: null,
    })

    expect(columns.map((column) => column.header)).toEqual([
      t('boughtItems.catalogue.columns.created'),
      'Created By',
      t('boughtItems.catalogue.columns.changed'),
      'Changed By',
      'Link',
    ])
    expect(columns.map((column) => column.value(item)).slice(0, 4)).toEqual([
      { iso: '2026-03-01T08:00:00Z' },
      'Ada Lovelace',
      { iso: '2026-04-01T08:00:00Z' },
      null,
    ])
  })

  it('makes the weblink clickable and leaves empty values empty', () => {
    const withLink = exportedRow(['weblink', 'note'], makeBoughtItemResponse({ weblink: 'https://acme.example/m6' }))
    const without = exportedRow(['weblink', 'product_family'], makeBoughtItemResponse())

    expect(withLink[t('boughtItems.catalogue.columns.weblink')]).toEqual({
      text: 'https://acme.example/m6',
      url: 'https://acme.example/m6',
    })
    expect(withLink[t('boughtItems.catalogue.columns.note')]).toBeNull()
    expect(without[t('boughtItems.catalogue.columns.weblink')]).toBeNull()
    expect(without[t('boughtItems.catalogue.columns.productFamily')]).toBeNull()
  })
})
