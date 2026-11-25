import { describe, it, expect } from 'vitest'

import { buildProductionPlanning, computeProductionSchedule } from '../productionPlanningTasks'
import { makeProductionOrderResponse } from '@/test-utils/factories'

import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'

// After every timestamp below, so no projection is floored at now.
const NOW = new Date('2026-03-09T12:00:00Z')

function makeOrder(overrides: Partial<ProductionOrderResponse> = {}): ProductionOrderResponse {
  return makeProductionOrderResponse({
    created: '2026-03-01',
    estimated_duration_minutes: 240,
    can_start: false,
    interruptions: [],
    ...overrides,
  })
}

// Started Monday 08:00, paused at 10:00, resumed Wednesday 09:00.
function resumedOrder(overrides: Partial<ProductionOrderResponse> = {}): ProductionOrderResponse {
  return makeOrder({
    status: 'in_progress',
    actual_start: '2026-03-02T08:00:00Z',
    interruptions: [{ paused_at: '2026-03-02T10:00:00Z', resumed_at: '2026-03-04T09:00:00Z', reason: null, paused_operator_id: null }],
    ...overrides,
  })
}

// The projection snaps to the start of the local day.
function localDayStart(iso: string): Date {
  const day = new Date(iso)
  day.setHours(0, 0, 0, 0)
  return day
}

function projectedStart(order: ProductionOrderResponse): Date | undefined {
  return computeProductionSchedule({
    machines: [{ id: 1, internal_name: 'Machine 1' }],
    orders: [order],
    lots: [],
    orderedDateByPositionId: new Map(),
    now: NOW,
  }).get(order.id)?.start
}

function projectedEnd(order: ProductionOrderResponse): Date | undefined {
  return computeProductionSchedule({
    machines: [{ id: 1, internal_name: 'Machine 1' }],
    orders: [order],
    lots: [],
    orderedDateByPositionId: new Map(),
    now: NOW,
  }).get(order.id)?.end
}

describe('computeProductionSchedule for a started order', () => {
  it('projects a resumed order from its latest resume, not its first start', () => {
    expect(projectedStart(resumedOrder())).toEqual(localDayStart('2026-03-04T09:00:00Z'))
  })

  it('projects a paused order from the run before its open interruption', () => {
    const order = resumedOrder({
      status: 'paused',
      interruptions: [
        { paused_at: '2026-03-02T10:00:00Z', resumed_at: '2026-03-04T09:00:00Z', reason: null, paused_operator_id: null },
        { paused_at: '2026-03-05T14:00:00Z', resumed_at: null, reason: null, paused_operator_id: null },
      ],
    })

    expect(projectedStart(order)).toEqual(localDayStart('2026-03-04T09:00:00Z'))
  })

  it('ends a running order at its stretched planned end once it overruns', () => {
    const order = makeOrder({
      status: 'in_progress',
      actual_start: '2026-03-02T08:00:00Z',
      planned_end: '2026-03-06T15:00:00Z',
    })

    expect(projectedEnd(order)).toEqual(localDayStart('2026-03-06T15:00:00Z'))
  })

  it('keeps the estimate when the planned end is earlier', () => {
    const order = makeOrder({
      status: 'in_progress',
      actual_start: '2026-03-02T08:00:00Z',
      planned_end: '2026-03-02T09:00:00Z',
    })

    expect(projectedEnd(order)!.getTime()).toBeGreaterThan(
      localDayStart('2026-03-02T09:00:00Z').getTime(),
    )
  })

  it('projects an order that was never paused from its actual start', () => {
    const order = makeOrder({ status: 'in_progress', actual_start: '2026-03-02T08:00:00Z' })

    expect(projectedStart(order)).toEqual(localDayStart('2026-03-02T08:00:00Z'))
  })
})

describe('buildProductionPlanning for a started order', () => {
  it('starts the gantt bar of a resumed order at its latest resume', () => {
    const { tasks } = buildProductionPlanning({
      machines: [{ id: 1, internal_name: 'Machine 1', fabricationMethods: [] }],
      orders: [resumedOrder()],
      lots: [],
      orderedDateByPositionId: new Map(),
      now: NOW,
      noAssignmentLabel: 'No assignment',
      externalLabel: 'External',
      dateUnknownSuffix: ' (date unknown)',
      madeItemLabel: (partNumber, revision) => `${partNumber}:${revision}`,
    })

    const bar = tasks.find((task) => task.id === 'production-order-1')
    expect(bar?.start).toEqual(localDayStart('2026-03-04T09:00:00Z'))
  })
})
