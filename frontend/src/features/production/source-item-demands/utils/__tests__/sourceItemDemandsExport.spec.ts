import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { makeBoughtItemResponse, makeSourceItemDemandResponse } from '@/test-utils/factories'
import { sourceItemDemandsExportColumns } from '../sourceItemDemandsExport'

import type { SourceItemDemandResponse } from '@/features/source-items'

const t = (key: string): string => i18n.global.t(key)

function exported(demand: SourceItemDemandResponse) {
  const columns = sourceItemDemandsExportColumns(t, () => null)
  return Object.fromEntries(columns.map((column) => [column.header, column.value(demand)]))
}

describe('sourceItemDemandsExportColumns', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('describes a source item by its dimension, material and type and links it', () => {
    const values = exported(makeSourceItemDemandResponse({ lot_number: 'L-12' }))

    expect(values[t('sourceItems.demands.columns.item')]).toBe('10mm')
    expect(values[t('sourceItems.catalogue.columns.material')]).toBe('Steel')
    expect(values[t('sourceItems.catalogue.columns.type')]).toBe('Rod')
    expect(values[t('sourceItems.demands.columns.lot')]).toBe('L-12')
    expect(values['Item Link']).toMatchObject({ url: expect.stringContaining('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb') })
  })

  it('describes a bought item by its article name, order code and manufacturer', () => {
    const values = exported(
      makeSourceItemDemandResponse({
        source_item: null,
        source_item_id: null,
        bought_item: makeBoughtItemResponse({ article_name: 'Round bar', order_code_1: 'RB-20', public_id: 'bi-9' }),
      }),
    )

    expect(values[t('sourceItems.demands.columns.item')]).toBe('Round bar')
    expect(values[t('sourceItems.catalogue.columns.orderCode1')]).toBe('RB-20')
    expect(values[t('sourceItems.demands.columns.manufacturer')]).toBe('Acme')
    expect(values[t('sourceItems.catalogue.columns.material')]).toBeNull()
    expect(values['Item Link']).toMatchObject({ url: expect.stringContaining('/resolve/bi-9') })
  })

  it('has no priority column, as the table shows none', () => {
    const headers = sourceItemDemandsExportColumns(t, () => null).map((column) => column.header)

    expect(headers).not.toContain(t('boughtItems.demands.columns.highPriority'))
    expect(headers.at(-1)).toBe('Item Link')
  })
})
