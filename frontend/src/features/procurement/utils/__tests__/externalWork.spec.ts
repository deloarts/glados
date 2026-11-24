import { describe, expect, it } from 'vitest'

import {
  externalWorkGroupLabel,
  externalWorkStage,
  isCriticalExternalWork,
  summarizeExternalWorkGroup,
} from '../externalWork'
import { makeExternalWorkRow } from '../../__tests__/externalWorkFixtures'

const localize = (text: Record<string, string>) => text.deAT ?? ''

describe('externalWorkStage', () => {
  it('is not assigned without a supplier line', () => {
    expect(externalWorkStage(makeExternalWorkRow())).toBe('unassigned')
  })

  it('follows the line until pieces are handed over', () => {
    const ordered = makeExternalWorkRow({ order_item_id: 5, order_item_status: 'ordered' })
    expect(externalWorkStage(ordered)).toBe('ordered')
    expect(externalWorkStage({ ...ordered, order_item_status: 'pending' })).toBe('pending')
    expect(externalWorkStage({ ...ordered, order_item_status: 'requested' })).toBe('requested')
    expect(externalWorkStage({ ...ordered, handed_over_quantity: 4 })).toBe('at_supplier')
    expect(
      externalWorkStage({ ...ordered, handed_over_quantity: 4, order_item_status: 'partially_delivered' }),
    ).toBe('partially_back')
  })
})

describe('externalWorkGroupLabel', () => {
  it('groups by the methods or by the supplier, the suggestion standing in for a line', () => {
    const unassigned = makeExternalWorkRow({ suggested_supplier_name: 'Härterei A' })
    const ordered = makeExternalWorkRow({ order_item_id: 5, supplier_name: 'Verzinkerei B' })

    expect(externalWorkGroupLabel(unassigned, 'method', localize)).toBe('Härten')
    expect(externalWorkGroupLabel(unassigned, 'supplier', localize)).toBe('Härterei A')
    expect(externalWorkGroupLabel(ordered, 'supplier', localize)).toBe('Verzinkerei B')
  })
})

describe('summarizeExternalWorkGroup', () => {
  it('counts the rows, the critical ones and the next latest pickup still open', () => {
    const summary = summarizeExternalWorkGroup([
      makeExternalWorkRow({ latest_pickup_date: '2026-11-25' }),
      makeExternalWorkRow({ latest_pickup_date: '2026-11-18', alert: 'overdue' }),
      makeExternalWorkRow({ latest_pickup_date: '2026-11-10', handed_over_quantity: 3 }),
      makeExternalWorkRow({ latest_pickup_date: null, alert: 'no_target_date' }),
    ])

    expect(summary).toEqual({ count: 4, critical: 1, nextLatestPickup: '2026-11-18' })
  })

  it('treats a missing target date as a note, not as critical', () => {
    expect(isCriticalExternalWork(makeExternalWorkRow({ alert: 'no_target_date' }))).toBe(false)
    expect(isCriticalExternalWork(makeExternalWorkRow({ alert: 'not_ready_in_time' }))).toBe(true)
  })
})
