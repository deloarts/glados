import { afterEach, describe, expect, it } from 'vitest'

import type { ITask } from '@svar-ui/vue-gantt'
import { buildOrderGanttTasks, filterOrdersForTimeline } from '../ordersGanttTasks'
import { setDisplayTimezone } from '@/core/utils/dates'
import type { OrderResponse } from '@/features/orders/types/ordersResponse'

afterEach(() => {
  setDisplayTimezone(null)
})

// ITask types start/end as optional, so narrow once here rather than
// non-null-asserting at every expectation.
function spanOf(tasks: ITask[], index = 0): { start: Date; end: Date } {
  const task = tasks[index]
  if (!task?.start || !task?.end) {
    throw new Error(`expected task #${index} to have both a start and an end`)
  }
  return { start: task.start, end: task.end }
}

function orderWith(overrides: Partial<OrderResponse> = {}): OrderResponse {
  return {
    id: 1,
    order_number: 'ORD-1',
    supplier_name: 'Supplier',
    status: 'ordered',
    created: '2026-08-01T08:00:00+00:00',
    changed: null,
    ordered_date: null,
    expected_delivery_date: null,
    delivery_date: null,
    items: [],
    ...overrides,
  } as unknown as OrderResponse
}

describe('buildOrderGanttTasks', () => {
  it('snaps a timestamped span to whole days', () => {
    // The chart is day-granular (a zero-length task is padded by exactly one
    // day), so a bar must not start at whatever o'clock the order happened to
    // be submitted.
    setDisplayTimezone('Europe/Vienna')
    const tasks = buildOrderGanttTasks([
      orderWith({
        ordered_date: '2026-08-03T14:32:11+00:00',
        delivery_date: '2026-08-07T09:05:00+00:00',
      }),
    ])

    expect(tasks).toHaveLength(1)
    const { start, end } = spanOf(tasks)
    expect(start.getHours()).toBe(0)
    expect(start.getMinutes()).toBe(0)
    expect(end.getHours()).toBe(0)
    expect(start.getDate()).toBe(3)
    expect(end.getDate()).toBe(7)
  })

  it('lines a timestamped ordered_date up with a calendar expected_delivery_date', () => {
    // ordered_date is an instant and expected_delivery_date a picked day; a
    // same-day pair must collapse to a zero-length span, not a few hours.
    setDisplayTimezone('Europe/Vienna')
    const { start, end } = spanOf(
      buildOrderGanttTasks([
        orderWith({
          ordered_date: '2026-08-03T14:32:11+00:00',
          expected_delivery_date: '2026-08-03',
        }),
      ]),
    )
    expect(start.getTime()).toBe(end.getTime())
  })

  it('orders start before end even when delivery precedes the ordered date', () => {
    setDisplayTimezone('Europe/Vienna')
    const { start, end } = spanOf(
      buildOrderGanttTasks([
        orderWith({
          ordered_date: '2026-08-07T09:00:00+00:00',
          delivery_date: '2026-08-03T09:00:00+00:00',
        }),
      ]),
    )
    expect(start.getTime()).toBeLessThanOrEqual(end.getTime())
    expect(start.getDate()).toBe(3)
  })

  it('skips an order with no dates at all rather than inventing a bar', () => {
    expect(buildOrderGanttTasks([orderWith()])).toEqual([])
  })
})

describe('filterOrdersForTimeline', () => {
  const NOW = new Date('2026-08-06T12:00:00Z')

  it('keeps a recently delivered order and drops a long-settled one', () => {
    setDisplayTimezone('Europe/Vienna')
    const recent = orderWith({
      id: 1,
      status: 'delivered',
      delivery_date: '2026-08-05T16:00:00+00:00',
    })
    const old = orderWith({
      id: 2,
      status: 'delivered',
      delivery_date: '2026-05-01T16:00:00+00:00',
    })

    const kept = filterOrdersForTimeline([recent, old], {}, NOW)

    expect(kept.map((o) => o.id)).toEqual([1])
  })

  it('always keeps an active order regardless of its dates', () => {
    const active = orderWith({ status: 'ordered', ordered_date: '2020-01-01T00:00:00+00:00' })
    expect(filterOrdersForTimeline([active], {}, NOW)).toHaveLength(1)
  })
})
