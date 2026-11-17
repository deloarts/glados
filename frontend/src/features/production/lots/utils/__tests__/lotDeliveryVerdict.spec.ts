import { describe, it, expect, afterEach } from 'vitest'

import { buildLotDeliveryVerdict } from '../lotDeliveryVerdict'
import { setDisplayTimezone } from '@/core/utils/dates'
import { makeLotResponse, makeProductionOrderResponse } from '@/test-utils/factories'

import type { LotDeliveryVerdictInput } from '../lotDeliveryVerdict'
import type { LotPositionResponse, LotResponse } from '../../../types/productionLotsResponse'
import type { ProductionOrderResponse } from '../../../types/productionOrdersResponse'

afterEach(() => {
  setDisplayTimezone(null)
})

function makePosition(overrides: Partial<LotPositionResponse> = {}): LotPositionResponse {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    created: '2026-07-01',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    sequence: 1,
    kind: 'internal',
    status: 'in_progress',
    quantity: 10,
    quantity_completed: 4,
    quantity_remaining: 6,
    note: null,
    creator_id: 1,
    lot_id: 1,
    steps: [],
    order_item_id: null,
    order_id: null,
    order_number: '',
    supplier_name: '',
    order_item_status: '',
    order_item_closed_short: false,
    earlier_order_lines: [],
    expected_delivery_date: null,
    production_orders: [],
    actions: [],
    planned_delivery_date: null,
    planned_pickup_date: null,
    ...overrides,
  }
}

function makeLot(overrides: Partial<LotResponse> = {}): LotResponse {
  return makeLotResponse({
    required_delivery_date: '2026-08-10',
    source_item_id: 5,
    source_label: 'Stock item',
    positions: [makePosition()],
    ...overrides,
  })
}

function makeOrder(overrides: Partial<ProductionOrderResponse> = {}): ProductionOrderResponse {
  return makeProductionOrderResponse({
    production_order_number: 'PO-0001',
    quantity: 5,
    machine_internal_name: 'Mill 1',
    lot_number: 'LOT-0001',
    ...overrides,
  })
}

function verdict(overrides: Partial<LotDeliveryVerdictInput> = {}) {
  return buildLotDeliveryVerdict({
    lot: makeLot(),
    productionOrders: [],
    today: '2026-08-01',
    ...overrides,
  })
}

describe('buildLotDeliveryVerdict', () => {
  it('returns null when the lot has no required delivery date', () => {
    expect(verdict({ lot: makeLot({ required_delivery_date: null }) })).toBeNull()
  })

  it('returns null for a canceled lot - the question no longer applies', () => {
    expect(verdict({ lot: makeLot({ status: 'canceled' }) })).toBeNull()
  })

  it('reports deliveryLate once today is past the required date, with an exact day count', () => {
    const v = verdict({
      lot: makeLot({ required_delivery_date: '2026-08-01' }),
      today: '2026-08-05',
    })
    expect(v?.id).toBe('deliveryLate')
    expect(v?.tooltipParams).toEqual({ count: 4 })
  })

  it('computes the day count exactly across a month boundary', () => {
    const v = verdict({
      lot: makeLot({ required_delivery_date: '2026-01-30' }),
      today: '2026-02-02',
    })
    expect(v?.id).toBe('deliveryLate')
    expect(v?.tooltipParams).toEqual({ count: 3 })
  })

  it('computes the day count exactly across a DST transition (UTC calendar math, not local Date subtraction)', () => {
    const v = verdict({
      lot: makeLot({ required_delivery_date: '2026-03-28' }),
      today: '2026-04-02',
    })
    expect(v?.id).toBe('deliveryLate')
    expect(v?.tooltipParams).toEqual({ count: 5 })
  })

  it('is not late when the required date is today', () => {
    const v = verdict({
      lot: makeLot({ required_delivery_date: '2026-08-05' }),
      today: '2026-08-05',
    })
    expect(v?.id).not.toBe('deliveryLate')
  })

  it('forecasts willBeLate from a single order whose planned_end lands after the required date', () => {
    const v = verdict({
      lot: makeLot({ required_delivery_date: '2026-08-05' }),
      productionOrders: [makeOrder({ planned_end: '2026-08-08T12:00:00' })],
      today: '2026-08-01',
    })
    expect(v?.id).toBe('deliveryWillBeLate')
    expect(v?.tooltipParams).toEqual({ count: 3 })
  })

  it('reports onTrack when the forecast is within the required date and every position is covered', () => {
    const v = verdict({
      lot: makeLot({ required_delivery_date: '2026-08-10' }),
      productionOrders: [makeOrder({ planned_end: '2026-08-08T12:00:00' })],
      today: '2026-08-01',
    })
    expect(v?.id).toBe('deliveryOnTrack')
  })

  it('reports due, not onTrack, for an unassigned position - coverage is incomplete, not on track', () => {
    const v = verdict({
      lot: makeLot({
        required_delivery_date: '2026-08-10',
        positions: [makePosition({ kind: 'unassigned' })],
      }),
      today: '2026-08-01',
    })
    expect(v?.id).toBe('deliveryDue')
  })

  it('reports due when an internal position has no order with a planned_end yet', () => {
    const v = verdict({
      lot: makeLot({ required_delivery_date: '2026-08-10' }),
      productionOrders: [makeOrder({ planned_end: null })],
      today: '2026-08-01',
    })
    expect(v?.id).toBe('deliveryDue')
  })

  it('ignores a canceled order even with a far-future planned_end, once another live order covers the position', () => {
    const v = verdict({
      lot: makeLot({ required_delivery_date: '2026-08-10' }),
      productionOrders: [
        makeOrder({ id: 1, status: 'canceled', planned_end: '2099-01-01T12:00:00' }),
        makeOrder({ id: 2, status: 'queued', planned_end: '2026-08-05T12:00:00' }),
      ],
      today: '2026-08-01',
    })
    expect(v?.id).toBe('deliveryOnTrack')
  })

  it("uses a completed order's actual_end, not its earlier planned_end", () => {
    const v = verdict({
      lot: makeLot({ required_delivery_date: '2026-08-05' }),
      productionOrders: [
        makeOrder({
          status: 'completed',
          planned_end: '2026-08-03T12:00:00',
          actual_end: '2026-08-10T12:00:00',
        }),
      ],
      today: '2026-08-01',
    })
    expect(v?.id).toBe('deliveryWillBeLate')
  })

  it('forecasts an undelivered external position from expected_delivery_date', () => {
    const v = verdict({
      lot: makeLot({
        required_delivery_date: '2026-08-05',
        positions: [makePosition({ kind: 'external', expected_delivery_date: '2026-08-08' })],
      }),
      today: '2026-08-01',
    })
    expect(v?.id).toBe('deliveryWillBeLate')
    expect(v?.tooltipParams).toEqual({ count: 3 })
  })

  it('forecasts a delivered external position from its actual delivery date, not the stale expected one', () => {
    const v = verdict({
      lot: makeLot({
        required_delivery_date: '2026-08-05',
        positions: [
          makePosition({ id: 7, kind: 'external', expected_delivery_date: '2026-08-08' }),
        ],
      }),
      externalDeliveryDates: { 7: '2026-08-03T12:00:00' },
      today: '2026-08-01',
    })
    expect(v?.id).toBe('deliveryOnTrack')
  })

  it('reports completedOnTime when the derived completion date is within the required date', () => {
    const v = verdict({
      lot: makeLot({ status: 'completed', required_delivery_date: '2026-08-05' }),
      productionOrders: [makeOrder({ status: 'completed', actual_end: '2026-08-02T12:00:00' })],
    })
    expect(v?.id).toBe('deliveryCompletedOnTime')
  })

  it('reports completedLate with an exact day count when the derived completion date is past the required date', () => {
    const v = verdict({
      lot: makeLot({ status: 'completed', required_delivery_date: '2026-08-05' }),
      productionOrders: [makeOrder({ status: 'completed', actual_end: '2026-08-08T12:00:00' })],
    })
    expect(v?.id).toBe('deliveryCompletedLate')
    expect(v?.tooltipParams).toEqual({ count: 3 })
  })

  it('derives completion as the max across an internal order and an external delivery, not either alone', () => {
    const onTime = verdict({
      lot: makeLot({
        status: 'completed',
        required_delivery_date: '2026-08-05',
        positions: [
          makePosition({ id: 1, kind: 'internal' }),
          makePosition({ id: 2, kind: 'external' }),
        ],
      }),
      productionOrders: [
        makeOrder({
          id: 1,
          lot_position_id: 1,
          status: 'completed',
          actual_end: '2026-08-02T12:00:00',
        }),
      ],
      externalDeliveryDates: { 2: '2026-08-04T12:00:00' },
    })
    expect(onTime?.id).toBe('deliveryCompletedOnTime')

    const late = verdict({
      lot: makeLot({
        status: 'completed',
        required_delivery_date: '2026-08-05',
        positions: [
          makePosition({ id: 1, kind: 'internal' }),
          makePosition({ id: 2, kind: 'external' }),
        ],
      }),
      productionOrders: [
        makeOrder({
          id: 1,
          lot_position_id: 1,
          status: 'completed',
          actual_end: '2026-08-02T12:00:00',
        }),
      ],
      externalDeliveryDates: { 2: '2026-08-08T12:00:00' },
    })
    expect(late?.id).toBe('deliveryCompletedLate')
  })

  it("resolves a late-evening UTC completion instant in the user's timezone, not by truncating the raw string", () => {
    setDisplayTimezone('Asia/Tokyo') // UTC+9, shifts 20:00 UTC into the next calendar day
    const v = verdict({
      lot: makeLot({ status: 'completed', required_delivery_date: '2026-08-04' }),
      productionOrders: [makeOrder({ status: 'completed', actual_end: '2026-08-04T20:00:00Z' })],
    })
    // A raw occurredAt.slice(0, 10) would read '2026-08-04' and call this on
    // time; in Asia/Tokyo it is already the 5th.
    expect(v?.id).toBe('deliveryCompletedLate')
  })

  it('falls back to the lot_completed event timestamp when no order or order-item date is derivable', () => {
    const v = verdict({
      lot: makeLot({
        status: 'completed',
        required_delivery_date: '2026-08-15',
        positions: [makePosition({ kind: 'unassigned' })],
      }),
      productionOrders: [],
      completedAt: '2026-08-10T12:00:00',
    })
    expect(v?.id).toBe('deliveryCompletedOnTime')
  })

  it('returns null for a completed lot when nothing is derivable and no event timestamp is given either', () => {
    const v = verdict({
      lot: makeLot({
        status: 'completed',
        required_delivery_date: '2026-08-15',
        positions: [makePosition({ kind: 'unassigned' })],
      }),
      productionOrders: [],
      completedAt: null,
    })
    expect(v).toBeNull()
  })
})
