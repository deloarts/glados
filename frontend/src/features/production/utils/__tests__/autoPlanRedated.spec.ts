import { describe, it, expect } from 'vitest'

import { formatWait, redatedReasonText, redatedShift, shiftSeverity } from '../autoPlanRedated'

import type { RedatedOrder } from '../autoPlanRedated'
import type { Schemas } from '@/core/api/generated'

type Reason = Schemas['RedatedOrderReasonResponse']

function reason(overrides: Partial<Reason> = {}): Reason {
  return {
    kind: 'ready_now',
    day: null,
    moment: null,
    previous_order_id: null,
    previous_order_number: null,
    previous_running: false,
    previous_overrun: false,
    previous_pieces_processed: null,
    previous_quantity: null,
    predecessor_sequence: null,
    predecessor_order_number: null,
    method_name: {},
    wait_after_minutes: 0,
    order_item_id: null,
    expected_date: null,
    late: false,
    arrived: false,
    forecast: false,
    response_time_days: 0,
    pieces_processed: null,
    quantity: null,
    overrun: false,
    ...overrides,
  }
}

function row(overrides: Partial<RedatedOrder> = {}): RedatedOrder {
  return {
    order_id: 6,
    production_order_number: 'PON-26-00006',
    lot_id: 6,
    lot_number: 'LOT-26-00006',
    made_item_part_number: 'TN-1',
    made_item_revision: '0',
    column: 'inspection',
    machine_id: null,
    machine_pool_id: null,
    before_planned_start: '2026-12-11T06:50:00Z',
    before_planned_end: '2026-12-11T07:05:00Z',
    after_planned_start: '2026-11-25T11:21:00Z',
    after_planned_end: '2026-11-25T11:36:00Z',
    reason: reason(),
    ...overrides,
  }
}

describe('redatedShift', () => {
  it('counts the local days the start moved', () => {
    expect(redatedShift(row())).toEqual({ kind: 'earlier', days: 16 })
    expect(
      redatedShift(row({ before_planned_start: '2026-12-01T08:00:00Z', after_planned_start: '2026-12-07T08:00:00Z' })),
    ).toEqual({ kind: 'later', days: 6 })
  })

  it('names an order that got or lost its date', () => {
    expect(redatedShift(row({ before_planned_start: null, before_planned_end: null })).kind).toBe('dated')
    expect(redatedShift(row({ after_planned_start: null, after_planned_end: null })).kind).toBe('undated')
  })

  it('falls back to the end when only the end moved to another day', () => {
    const moved = row({
      before_planned_start: '2026-11-25T08:00:00Z',
      after_planned_start: '2026-11-25T08:00:00Z',
      before_planned_end: '2026-11-25T09:00:00Z',
      after_planned_end: '2026-11-27T09:00:00Z',
    })
    expect(redatedShift(moved)).toEqual({ kind: 'later', days: 2 })
  })
})

describe('shiftSeverity', () => {
  it('marks earlier green, later amber and a late order line red', () => {
    expect(shiftSeverity(row(), redatedShift(row()))).toBe('success')
    const later = row({ before_planned_start: '2026-11-20T08:00:00Z' })
    expect(shiftSeverity(later, redatedShift(later))).toBe('warn')
    const late = row({ reason: reason({ kind: 'order_line', late: true }) })
    expect(shiftSeverity(late, redatedShift(late))).toBe('danger')
  })
})

describe('formatWait', () => {
  it('shows whole hours in hours and the rest in minutes', () => {
    expect(formatWait(480)).toBe('8 h')
    expect(formatWait(90)).toBe('90 min')
  })
})

describe('redatedReasonText', () => {
  it('names the order line and whether it is late', () => {
    const late = redatedReasonText(
      reason({ kind: 'order_line', order_item_id: 45, late: true, expected_date: '2026-12-10', response_time_days: 1 }),
    )
    expect(late.key).toBe('productionSchedule.autoPlan.redated.reason.orderLineLate')
    expect(late.params).toEqual({ line: 45 })
    expect(late.detailParams.days).toBe(1)
    const due = redatedReasonText(reason({ kind: 'order_line', order_item_id: 46 }))
    expect(due.key).toBe('productionSchedule.autoPlan.redated.reason.orderLine')
  })

  it('names the wait after a predecessor and the order ahead on the queue', () => {
    const wait = redatedReasonText(
      reason({ kind: 'predecessor', wait_after_minutes: 480, predecessor_sequence: 2, moment: '2026-11-26T22:40:00Z' }),
    )
    expect(wait.key).toBe('productionSchedule.autoPlan.redated.reason.waitAfter')
    expect(wait.params).toEqual({ duration: '8 h' })
    const running = redatedReasonText(
      reason({
        kind: 'queue',
        previous_order_number: 'PON-26-00010',
        previous_running: true,
        previous_overrun: true,
        previous_pieces_processed: 6,
        previous_quantity: 10,
      }),
    )
    expect(running.key).toBe('productionSchedule.autoPlan.redated.reason.queueRunning')
    expect(running.detailKey).toBe('productionSchedule.autoPlan.redated.reason.queueOverrunDetail')
    expect(running.detailParams).toMatchObject({ processed: 6, quantity: 10, left: 4 })
  })

  it('names a step at a supplier known only by its forecast, and a line that arrived', () => {
    const forecast = redatedReasonText(reason({ kind: 'order_line', forecast: true, expected_date: '2026-12-01' }))
    expect(forecast.key).toBe('productionSchedule.autoPlan.redated.reason.orderLineForecast')
    expect(forecast.detailKey).toBe('productionSchedule.autoPlan.redated.reason.orderLineForecastDetail')
    const arrived = redatedReasonText(reason({ kind: 'order_line', order_item_id: 52, arrived: true }))
    expect(arrived.key).toBe('productionSchedule.autoPlan.redated.reason.orderLine')
    expect(arrived.detailKey).toBe('productionSchedule.autoPlan.redated.reason.orderLineArrivedDetail')
  })

  it('leaves the order out of a predecessor detail that has none', () => {
    const text = redatedReasonText(
      reason({ kind: 'predecessor', predecessor_sequence: 2, moment: '2026-11-26T09:00:00Z' }),
    )
    expect(text.detailKey).toBe('productionSchedule.autoPlan.redated.reason.predecessorReadyDetail')
    expect(text.detailParams).toMatchObject({ sequence: 2 })
  })

  it('says a walk that ran meanwhile dated an order without a reason', () => {
    expect(redatedReasonText(null).key).toBe('productionSchedule.autoPlan.redated.reason.walkedMeanwhile')
  })
})
