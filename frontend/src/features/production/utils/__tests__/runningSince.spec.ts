import { describe, it, expect } from 'vitest'

import { runningSince } from '../runningSince'

import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'

type Interruptions = NonNullable<ProductionOrderResponse['interruptions']>

function at(iso: string): Date {
  return new Date(iso)
}

describe('runningSince', () => {
  it('is null before the first start', () => {
    expect(runningSince({ actual_start: null, interruptions: [] })).toBeNull()
  })

  it('is the first start while the order has never been resumed', () => {
    expect(runningSince({ actual_start: '2026-03-02T08:00:00Z', interruptions: [] })).toEqual(
      at('2026-03-02T08:00:00Z'),
    )
    expect(runningSince({ actual_start: '2026-03-02T08:00:00Z', interruptions: [] })).toEqual(
      at('2026-03-02T08:00:00Z'),
    )
  })

  it('is the end of the latest closed interruption once the order was resumed', () => {
    const interruptions: Interruptions = [
      { paused_at: '2026-03-03T10:00:00Z', resumed_at: '2026-03-04T09:00:00Z', reason: null, paused_operator_id: null, pause_cause: null },
      { paused_at: '2026-03-02T10:00:00Z', resumed_at: '2026-03-02T11:00:00Z', reason: null, paused_operator_id: null, pause_cause: null },
    ]

    expect(runningSince({ actual_start: '2026-03-02T08:00:00Z', interruptions })).toEqual(
      at('2026-03-04T09:00:00Z'),
    )
  })

  it('finds the latest resume when the interruptions come oldest first', () => {
    // The backend lists interruptions oldest first, so the latest resume is
    // the last closed row, not the first one met.
    const interruptions: Interruptions = [
      { paused_at: '2026-03-02T10:00:00Z', resumed_at: '2026-03-02T11:00:00Z', reason: null, paused_operator_id: null, pause_cause: null },
      { paused_at: '2026-03-03T10:00:00Z', resumed_at: '2026-03-04T09:00:00Z', reason: null, paused_operator_id: null, pause_cause: null },
    ]

    expect(runningSince({ actual_start: '2026-03-02T08:00:00Z', interruptions })).toEqual(
      at('2026-03-04T09:00:00Z'),
    )
  })

  it('ignores an interruption that is still open', () => {
    const interruptions: Interruptions = [
      { paused_at: '2026-03-02T10:00:00Z', resumed_at: '2026-03-02T11:00:00Z', reason: null, paused_operator_id: null, pause_cause: null },
      { paused_at: '2026-03-02T14:00:00Z', resumed_at: null, reason: null, paused_operator_id: null, pause_cause: null },
    ]

    expect(runningSince({ actual_start: '2026-03-02T08:00:00Z', interruptions })).toEqual(
      at('2026-03-02T11:00:00Z'),
    )
  })

  it('compares instants, not the text of differently written timestamps', () => {
    // 12:00 at +02:00 is 10:00 UTC, an hour before the resume at 11:00 UTC,
    // although the start sorts after the resume as text. A timestamp without
    // an offset is read as UTC.
    expect(
      runningSince({
        actual_start: '2026-03-02T12:00:00+02:00',
        interruptions: [{ paused_at: '2026-03-02T10:30:00', resumed_at: '2026-03-02T11:00:00', reason: null, paused_operator_id: null, pause_cause: null }],
      }),
    ).toEqual(at('2026-03-02T11:00:00Z'))
  })
})
