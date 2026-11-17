import { describe, expect, it } from 'vitest'

import { i18n } from '@/core/i18n'
import { makeOrderItemResponse, makeOrderResponse } from '@/test-utils/factories'
import { orderLineRows, ordersExportColumns } from '../ordersExport'

const t = (key: string): string => i18n.global.t(key)

describe('orderLineRows', () => {
  it('writes one row per line in position order and one for an order without lines', () => {
    const withLines = makeOrderResponse({
      id: 1,
      items: [makeOrderItemResponse({ id: 11, position: 2 }), makeOrderItemResponse({ id: 10, position: 1 })],
    })
    const empty = makeOrderResponse({ id: 2, items: [] })

    const rows = orderLineRows([withLines, empty])

    expect(rows.map((row) => [row.order.id, row.line?.id ?? null])).toEqual([
      [1, 10],
      [1, 11],
      [2, null],
    ])
  })
})

describe('ordersExportColumns', () => {
  function exported(row: ReturnType<typeof orderLineRows>[number]) {
    const columns = ordersExportColumns(t, 'EUR')
    return Object.fromEntries(columns.map((column) => [column.header, column.value(row)]))
  }

  it('repeats the order fields on each line and writes prices as numbers in the currency', () => {
    const order = makeOrderResponse({ order_number: 'ORD-7', status: 'ordered', supplier_name: 'Acme' })
    const line = makeOrderItemResponse({ quantity: 4, price: 1250, quantity_delivered: 1, status: 'ordered' })

    const values = exported({ order, line })

    expect(values[t('orders.columns.orderNumber')]).toBe('ORD-7')
    expect(values['Order Status']).toBe(t('orders.status.ordered'))
    expect(values[t('orders.columns.supplier')]).toBe('Acme')
    expect(values[t('orders.items.columns.quantity')]).toBe(4)
    expect(values['Delivered Qty']).toBe(1)
    expect(values[`${t('orders.items.columns.price')} (EUR)`]).toEqual({ value: 12.5, format: '#,##0.00' })
    expect(values[`${t('orders.items.columns.pricePosition')} (EUR)`]).toEqual({ value: 50, format: '#,##0.00' })
    expect(values['Line Status']).toBe(t('orders.items.status.ordered'))
    expect(values.Link).toEqual({
      text: `${window.location.origin}/resolve/${order.public_id}`,
      url: `${window.location.origin}/resolve/${order.public_id}`,
    })
  })

  it('leaves the line columns empty for an order without lines and an unpriced line without prices', () => {
    const order = makeOrderResponse()

    const empty = exported({ order, line: null })
    const unpriced = exported({ order, line: makeOrderItemResponse({ price: null }) })

    expect(empty[t('orders.items.columns.quantity')]).toBeNull()
    expect(empty['Line Status']).toBeNull()
    expect(empty[t('orders.columns.orderNumber')]).toBe(order.order_number)
    expect(unpriced[`${t('orders.items.columns.price')} (EUR)`]).toBeNull()
    expect(unpriced[`${t('orders.items.columns.pricePosition')} (EUR)`]).toBeNull()
  })
})
