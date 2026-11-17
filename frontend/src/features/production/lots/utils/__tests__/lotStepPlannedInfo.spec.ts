import { describe, it, expect } from 'vitest'

import { resolvePlannedStepInfo } from '../lotStepPlannedInfo'
import type {
  ActiveOrderForPlannedInfo,
  FullOrderForPlannedInfo,
  PlannedStepInfoInput,
} from '../lotStepPlannedInfo'
import type { LotPositionKind } from '../../../types/productionLotsResponse'

// LotStepList.vue's plannedInfoFor, its densest single piece of business
// logic (multi-candidate date resolution), tested here without mounting the
// table.

const AUTO_PLANNER = 'Auto-planner'

function position(kind: LotPositionKind, expectedDeliveryDate: string | null = null) {
  return { kind, expected_delivery_date: expectedDeliveryDate }
}

function activeOrder(overrides: Partial<ActiveOrderForPlannedInfo> = {}): ActiveOrderForPlannedInfo {
  return { id: 1, status: 'queued', ...overrides }
}

function fullOrder(overrides: Partial<FullOrderForPlannedInfo> = {}): FullOrderForPlannedInfo {
  return {
    planned_by: null,
    planned_end: null,
    planned_start: null,
    actual_end: null,
    actual_start: null,
    ...overrides,
  }
}

function resolve(input: Partial<PlannedStepInfoInput> & { position: PlannedStepInfoInput['position'] }) {
  return resolvePlannedStepInfo({
    activeOrder: null,
    fullOrder: undefined,
    autoPlannerLabel: AUTO_PLANNER,
    ...input,
  })
}

describe('resolvePlannedStepInfo', () => {
  it('returns all-null for an unassigned position', () => {
    expect(resolve({ position: position('unassigned') })).toEqual({
      date: null,
      startDate: null,
      plannedByLabel: null,
    })
  })

  it('an external position with no order uses its own expected_delivery_date, no start/plannedBy', () => {
    const result = resolve({ position: position('external', '2026-03-05T00:00:00Z') })

    expect(result.date).toEqual(new Date('2026-03-05T00:00:00Z'))
    expect(result.startDate).toBeNull()
    expect(result.plannedByLabel).toBeNull()
  })

  it('an external position with no expected_delivery_date resolves to all-null', () => {
    expect(resolve({ position: position('external', null) })).toEqual({
      date: null,
      startDate: null,
      plannedByLabel: null,
    })
  })

  it('an internal position with no active order resolves to all-null', () => {
    expect(resolve({ position: position('internal'), activeOrder: null })).toEqual({
      date: null,
      startDate: null,
      plannedByLabel: null,
    })
  })

  it('an internal position uses the order planned_end/planned_start while queued', () => {
    const result = resolve({
      position: position('internal'),
      activeOrder: activeOrder({ status: 'queued' }),
      fullOrder: fullOrder({
        planned_end: '2026-03-10T00:00:00Z',
        planned_start: '2026-03-08T00:00:00Z',
        planned_by: { full_name: 'Alice' },
      }),
    })

    expect(result.date).toEqual(new Date('2026-03-10T00:00:00Z'))
    expect(result.startDate).toEqual(new Date('2026-03-08T00:00:00Z'))
    expect(result.plannedByLabel).toBe('Alice')
  })

  it('a completed order uses actual_end/actual_start instead of the planned ones', () => {
    const result = resolve({
      position: position('internal'),
      activeOrder: activeOrder({ status: 'completed' }),
      fullOrder: fullOrder({
        planned_end: '2026-03-10T00:00:00Z',
        actual_end: '2026-03-12T00:00:00Z',
        planned_start: '2026-03-08T00:00:00Z',
        actual_start: '2026-03-09T00:00:00Z',
      }),
    })

    expect(result.date).toEqual(new Date('2026-03-12T00:00:00Z'))
    expect(result.startDate).toEqual(new Date('2026-03-09T00:00:00Z'))
  })

  it('falls back to the auto-planner label when the order has no planned_by', () => {
    const result = resolve({
      position: position('internal'),
      activeOrder: activeOrder(),
      fullOrder: fullOrder({ planned_end: '2026-03-10T00:00:00Z' }),
    })

    expect(result.plannedByLabel).toBe(AUTO_PLANNER)
  })

  it('a mixed position with both dates known shows the later as date, the earlier as startDate', () => {
    const result = resolve({
      position: position('mixed', '2026-03-15T00:00:00Z'),
      activeOrder: activeOrder({ status: 'queued' }),
      fullOrder: fullOrder({
        planned_end: '2026-03-05T00:00:00Z',
        planned_start: '2026-03-01T00:00:00Z',
      }),
    })

    // The external half finishes later (03-15) than the internal order
    // (03-05), so it wins as `date`; the internal order starts earlier
    // (03-01, external has no start of its own), so it wins as `startDate`.
    expect(result.date).toEqual(new Date('2026-03-15T00:00:00Z'))
    expect(result.startDate).toEqual(new Date('2026-03-01T00:00:00Z'))
  })

  it('a mixed position with only the external date known uses it, with a null startDate', () => {
    const result = resolve({
      position: position('mixed', '2026-03-15T00:00:00Z'),
      activeOrder: null,
    })

    expect(result.date).toEqual(new Date('2026-03-15T00:00:00Z'))
    expect(result.startDate).toBeNull()
    expect(result.plannedByLabel).toBeNull()
  })

  it('a mixed position with only the internal date known uses it', () => {
    const result = resolve({
      position: position('mixed', null),
      activeOrder: activeOrder({ status: 'queued' }),
      fullOrder: fullOrder({ planned_end: '2026-03-05T00:00:00Z' }),
    })

    expect(result.date).toEqual(new Date('2026-03-05T00:00:00Z'))
  })

  it('a mixed position with neither date known resolves to all-null', () => {
    const result = resolve({
      position: position('mixed', null),
      activeOrder: activeOrder(),
      fullOrder: fullOrder(),
    })

    expect(result).toEqual({ date: null, startDate: null, plannedByLabel: null })
  })
})
