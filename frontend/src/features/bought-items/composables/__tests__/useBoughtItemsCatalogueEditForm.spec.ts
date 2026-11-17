import { describe, it, expect } from 'vitest'

import { useBoughtItemsCatalogueEditForm } from '../useBoughtItemsCatalogueEditForm'

import type { BoughtItemResponse } from '../../types/boughtItemsResponse'
import type { LocalizedText } from '@/shared/utils/localizedText'

function makeItem(overrides: Partial<BoughtItemResponse> = {}): BoughtItemResponse {
  return {
    edit_version: 0,
    over_delivery_tolerance_percent: null,
    under_delivery_tolerance_percent: null,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    part_number: 'PN-1',
    status: 'active',
    archived: false,
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    order_code_1: 'OC1',
    order_code_2: 'OC2',
    gtin: '123',
    ean: '456',
    tariff_number: '789',
    article_name: 'Article',
    article_groups: [],
    data_source: 'WEB',
    mass: 100,
    note: 'Note',
    weblink: 'http://example.com',
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    manufacturer_id: 1,
    manufacturer_name: 'Manufacturer',
    pdf_files: [],
    edp_part_id: null,
    edp_synced_at: null,
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

type ArticleGroup = BoughtItemResponse['article_groups'][number]

function loc(text: string): LocalizedText {
  return { enGB: text }
}

// The form reads only a group's id.
function group(id: number): ArticleGroup {
  return { id, name: loc(`G${id}`) } as ArticleGroup
}

describe('useBoughtItemsCatalogueEditForm', () => {
  it('fills the form from one item', () => {
    const { form, mixedFields, fillFromSelection } = useBoughtItemsCatalogueEditForm(() => 'mixed')

    fillFromSelection([makeItem({ article_groups: [group(3), group(1)] })])

    expect(form.article_name).toBe('Article')
    expect(form.order_code_2).toBe('OC2')
    expect(form.article_group_ids).toEqual([1, 3])
    expect(mixedFields.size).toBe(0)
  })

  it('marks the fields the selection disagrees on as mixed, groups included', () => {
    const { form, mixedFields, placeholderFor, fillFromSelection } =
      useBoughtItemsCatalogueEditForm(() => 'mixed')

    fillFromSelection([
      makeItem({ id: 1, note: 'A', article_groups: [group(1)] }),
      makeItem({ id: 2, note: 'B', article_groups: [group(2)] }),
    ])

    expect(mixedFields.has('note')).toBe(true)
    expect(mixedFields.has('article_group_ids')).toBe(true)
    expect(mixedFields.has('article_name')).toBe(false)
    expect(placeholderFor('note')).toBe('mixed')
    expect(form.article_group_ids).toEqual([])
  })

  it('empties the form for an empty selection', () => {
    const { form, fillFromSelection } = useBoughtItemsCatalogueEditForm(() => 'mixed')
    fillFromSelection([makeItem()])

    fillFromSelection([])

    expect(form.article_name).toBe('')
    expect(form.manufacturer_id).toBeNull()
  })

  it('saves only the touched fields over each item', () => {
    const { form, markDirty, fillFromSelection, buildPayload } =
      useBoughtItemsCatalogueEditForm(() => 'mixed')
    const first = makeItem({ id: 1, note: 'A' })
    const second = makeItem({ id: 2, note: 'B', gtin: null })
    fillFromSelection([first, second])

    form.article_name = '  Renamed  '
    markDirty('article_name')
    form.weblink = '   '
    markDirty('weblink')

    const payload = buildPayload(second)
    expect(payload.article_name).toBe('Renamed')
    expect(payload.weblink).toBeNull()
    expect(payload.note).toBe('B')
    expect(payload.gtin).toBeNull()
    expect(payload.order_code_1).toBe('OC1')
  })

  it('accepts an untouched mixed required field and refuses a cleared one', () => {
    const { form, markDirty, fillFromSelection, isFormValid } =
      useBoughtItemsCatalogueEditForm(() => 'mixed')
    fillFromSelection([
      makeItem({ id: 1, article_name: 'A' }),
      makeItem({ id: 2, article_name: 'B' }),
    ])

    expect(isFormValid()).toBe(true)

    form.article_name = ' '
    markDirty('article_name')
    expect(isFormValid()).toBe(false)
  })
})
