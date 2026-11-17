import { describe, expect, it } from 'vitest'

import { i18n } from '@/core/i18n'
import { makeDemandItemResponse } from '@/test-utils/factories'
import { demandExportColumns } from '../demandExportColumns'

import type { BoughtItemDemandResponse } from '@/features/bought-items/types/boughtItemsDemandsResponse'

const t = (key: string): string => i18n.global.t(key)

function columns(priority?: boolean) {
  return demandExportColumns<BoughtItemDemandResponse>({
    t,
    prefix: 'boughtItems.demands',
    bucketName: (id) => (id === 3 ? 'Urgent' : null),
    itemColumns: [{ header: 'Item', value: (demand) => demand.item_article_name }],
    itemPublicId: (demand) => (demand.item_id === 1 ? 'item-1' : null),
    ...(priority === undefined ? {} : { priority }),
  })
}

function row(demand: BoughtItemDemandResponse, priority?: boolean) {
  return Object.fromEntries(columns(priority).map((column) => [column.header, column.value(demand)]))
}

describe('demandExportColumns', () => {
  it('puts the item columns between the project and the priority and ends with the item link', () => {
    expect(columns().map((column) => column.header)).toEqual([
      t('boughtItems.demands.columns.id'),
      t('boughtItems.demands.columns.status'),
      t('boughtItems.demands.buckets.column'),
      t('boughtItems.demands.columns.quantity'),
      'Unit',
      t('boughtItems.demands.columns.project'),
      'Customer',
      'Project Description',
      'Item',
      t('boughtItems.demands.columns.highPriority'),
      t('boughtItems.demands.columns.desiredDelivery'),
      t('boughtItems.demands.columns.created'),
      'Created By',
      'Note',
      'Item Link',
    ])
  })

  it('writes the stored status, the bucket name, the unit label and the priority as labels', () => {
    const values = row(makeDemandItemResponse({ status: 'fulfilled', bucket_id: 3, high_priority: true, quantity: 12 }))

    expect(values[t('boughtItems.demands.columns.status')]).toBe(t('boughtItems.demands.status.fulfilled'))
    expect(values[t('boughtItems.demands.buckets.column')]).toBe('Urgent')
    expect(values[t('boughtItems.demands.columns.quantity')]).toBe(12)
    expect(values.Unit).toBe(t('boughtItems.unitsShort.PCS'))
    expect(values[t('boughtItems.demands.columns.highPriority')]).toBe(t('common.yes'))
  })

  it('writes the dates as dates and links the demanded item', () => {
    const values = row(
      makeDemandItemResponse({ desired_delivery_date: '2026-12-01', created: '2026-11-01T07:00:00Z' }),
    )

    expect(values[t('boughtItems.demands.columns.desiredDelivery')]).toEqual({ iso: '2026-12-01' })
    expect(values[t('boughtItems.demands.columns.created')]).toEqual({ iso: '2026-11-01T07:00:00Z' })
    expect(values['Item Link']).toEqual({
      text: `${window.location.origin}/resolve/item-1`,
      url: `${window.location.origin}/resolve/item-1`,
    })
  })

  it('leaves the bucket and the link empty without them', () => {
    const values = row(makeDemandItemResponse({ bucket_id: null, item_id: 2 }))

    expect(values[t('boughtItems.demands.buckets.column')]).toBeNull()
    expect(values['Item Link']).toBeNull()
  })

  it('leaves out the priority for a kind whose table shows none', () => {
    expect(columns(false).map((column) => column.header)).not.toContain(
      t('boughtItems.demands.columns.highPriority'),
    )
  })
})
