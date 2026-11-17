import type { ITask } from '@svar-ui/vue-gantt'
import { DAY_MS, toLocalDayStart } from '@/core/utils/dates'
import type { OrderItemResponse, OrderResponse, OrderStatus } from '../types/ordersResponse'

const TIMELINE_ACTIVE_WINDOW_DAYS = 30
const ACTIVE_ORDER_STATUSES: OrderStatus[] = [
  'draft',
  'requested',
  'partially_ordered',
  'ordered',
  'partially_delivered',
]

interface DateSpan {
  start: Date
  end: Date
}

// The chart is day-granular, so instants and calendar dates both collapse
// to the start of their local day.
function toDate(value: string | null): Date | null {
  return value ? toLocalDayStart(value) : null
}

function resolveSpan(
  orderedDate: string | null,
  deliveredOrExpected: string | null,
): DateSpan | null {
  const start = toDate(orderedDate)
  const end = toDate(deliveredOrExpected)
  if (!start && !end) return null
  const resolvedStart = start ?? (end as Date)
  const resolvedEnd = end ?? (start as Date)
  return resolvedEnd < resolvedStart
    ? { start: resolvedEnd, end: resolvedStart }
    : { start: resolvedStart, end: resolvedEnd }
}

function overrides(itemValue: string | null, orderValue: string | null): boolean {
  return itemValue !== null && itemValue !== orderValue
}

function itemHasDistinctDates(order: OrderResponse, item: OrderItemResponse): boolean {
  return (
    overrides(item.ordered_date, order.ordered_date) ||
    overrides(item.expected_delivery_date, order.expected_delivery_date) ||
    overrides(item.delivery_date, order.delivery_date)
  )
}

function progressFor(deliveryDate: string | null, status: string): number {
  if (deliveryDate) return 100
  if (status === 'partially_delivered') return 50
  return 0
}

function becameInactiveDate(order: OrderResponse): Date | null {
  if (order.status === 'delivered') {
    return toDate(order.delivery_date ?? order.changed ?? order.created)
  }
  if (order.status === 'canceled') {
    return toDate(order.changed ?? order.created)
  }
  return null
}

interface TimelineFilterOptions {
  hideDelivered?: boolean
  hideCanceled?: boolean
}

export function filterOrdersForTimeline(
  orders: OrderResponse[],
  options: TimelineFilterOptions = {},
  now: Date = new Date(),
): OrderResponse[] {
  const cutoff = new Date(now.getTime() - TIMELINE_ACTIVE_WINDOW_DAYS * DAY_MS)

  return orders.filter((order) => {
    if (order.status === 'delivered' && options.hideDelivered) return false
    if (order.status === 'canceled' && options.hideCanceled) return false
    if (ACTIVE_ORDER_STATUSES.includes(order.status)) return true
    const inactiveSince = becameInactiveDate(order)
    return inactiveSince !== null && inactiveSince >= cutoff
  })
}

export function buildOrderGanttTasks(orders: OrderResponse[]): ITask[] {
  const tasks: ITask[] = []

  for (const order of orders) {
    const span = resolveSpan(
      order.ordered_date,
      order.delivery_date ?? order.expected_delivery_date,
    )
    if (!span) continue

    const distinctItems = (order.items ?? []).filter((item) => itemHasDistinctDates(order, item))

    tasks.push({
      id: `order-${order.id}`,
      text: `${order.order_number} (${order.supplier_name})`,
      start: span.start,
      end: span.end,
      progress: progressFor(order.delivery_date, order.status),
      type: distinctItems.length > 0 ? 'summary' : 'task',
      parent: 0,
      open: false,
      kind: 'order',
      status: order.status,
    })

    for (const item of distinctItems) {
      const itemOrderedDate = item.ordered_date ?? order.ordered_date
      const itemDeliveryDate = item.delivery_date ?? order.delivery_date
      const itemExpectedDate = item.expected_delivery_date ?? order.expected_delivery_date
      const itemSpan = resolveSpan(itemOrderedDate, itemDeliveryDate ?? itemExpectedDate)
      if (!itemSpan) continue

      tasks.push({
        id: `order-item-${item.id}`,
        text: item.item_article_name || item.item_specification || item.item_order_code_1,
        start: itemSpan.start,
        end: itemSpan.end,
        progress: progressFor(itemDeliveryDate, item.status),
        type: 'task',
        parent: `order-${order.id}`,
        kind: 'item',
        status: item.status,
      })
    }
  }

  return tasks
}
