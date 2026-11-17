import { dateCell, moneyCell, recordLinkCell, type SpreadsheetColumn } from '@/shared/spreadsheet-export'
import { formatUnit } from '@/shared/utils/units'

import type { OrderItemResponse, OrderResponse } from '../types/ordersResponse'

/** One sheet row of the orders export: an order line with its order. */
export interface OrderLineRow {
  order: OrderResponse
  /** Null for an order without lines, which still gets a row of its own. */
  line: OrderItemResponse | null
}

/**
 * The sheet rows of the exported orders: one per order line in position
 * order, with the order's fields repeated on each, and one for an order
 * without lines, so no order goes missing from the file.
 */
export function orderLineRows(orders: readonly OrderResponse[]): OrderLineRow[] {
  return orders.flatMap((order): OrderLineRow[] =>
    order.items.length === 0
      ? [{ order, line: null }]
      : [...order.items].sort((a, b) => a.position - b.position).map((line) => ({ order, line })),
  )
}

function lineValue<T>(read: (line: OrderItemResponse) => T) {
  return (row: OrderLineRow): T | null => (row.line ? read(row.line) : null)
}

/**
 * The export columns of the orders: the order's number, status, supplier
 * and order date, then the line's item, quantities, prices, status, project,
 * dates, storage place, note and receiver, and last the lasting link to the
 * order. Prices are numbers in the display currency, which the headers name.
 */
export function ordersExportColumns(
  t: (key: string) => string,
  currency: string,
): SpreadsheetColumn<OrderLineRow>[] {
  return [
    { header: t('orders.columns.orderNumber'), value: (row) => row.order.order_number },
    { header: t('orders.export.columns.orderStatus'), value: (row) => t(`orders.status.${row.order.status}`) },
    { header: t('orders.columns.supplier'), value: (row) => row.order.supplier_name },
    { header: t('orders.columns.orderedDate'), value: (row) => dateCell(row.order.ordered_date) },
    { header: t('orders.items.columns.position'), value: lineValue((line) => line.position) },
    {
      header: t('orders.items.columns.item'),
      value: lineValue((line) => line.item_article_name || line.virtual_name || null),
    },
    { header: t('orders.export.columns.partNumber'), value: lineValue((line) => line.item_part_number) },
    { header: t('orders.export.columns.orderCode'), value: lineValue((line) => line.item_order_code_1 || null) },
    { header: t('orders.export.columns.manufacturer'), value: lineValue((line) => line.item_manufacturer) },
    { header: t('orders.items.columns.quantity'), value: lineValue((line) => line.quantity) },
    { header: t('orders.items.columns.unit'), value: lineValue((line) => formatUnit(line.unit) || null) },
    {
      header: t('orders.export.columns.quantityDelivered'),
      value: lineValue((line) => line.quantity_delivered),
    },
    {
      header: `${t('orders.items.columns.price')} (${currency})`,
      value: lineValue((line) => moneyCell(line.price)),
    },
    {
      header: `${t('orders.items.columns.pricePosition')} (${currency})`,
      value: lineValue((line) => moneyCell(line.price === null ? null : line.price * line.quantity)),
    },
    {
      header: t('orders.export.columns.lineStatus'),
      value: lineValue((line) => t(`orders.items.status.${line.status}`)),
    },
    { header: t('orders.items.columns.project'), value: lineValue((line) => line.project_number || null) },
    {
      header: t('orders.items.columns.expectedDelivery'),
      value: lineValue((line) => dateCell(line.expected_delivery_date)),
    },
    { header: t('orders.items.columns.deliveryDate'), value: lineValue((line) => dateCell(line.delivery_date)) },
    { header: t('orders.items.columns.storagePlace'), value: lineValue((line) => line.storage_place) },
    { header: t('orders.items.columns.note'), value: lineValue((line) => line.note || null) },
    { header: t('orders.items.columns.receiver'), value: lineValue((line) => line.receiver?.full_name ?? null) },
    { header: t('spreadsheetExport.columns.link'), value: (row) => recordLinkCell(row.order.public_id) },
  ]
}
