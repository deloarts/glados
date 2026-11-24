import { describe, expect, it } from 'vitest'

import {
  groupExternalWorkBySupplier,
  summarizeExternalWork,
} from '../externalWorkGroups'
import type { ExternalWorkRow } from '../externalWorkGroups'

function row(overrides: Partial<ExternalWorkRow> = {}): ExternalWorkRow {
  return {
    lot_number: 'LOT-1',
    part_number: 'PN-1',
    item_name: 'Part',
    quantity: 1,
    methods: ['Hardening'],
    supplier_name: 'Hardener',
    supplier_suggested: true,
    latest_pickup_date: '2026-11-12',
    ready_from: null,
    ready_now: false,
    due_back_date: null,
    alert: null,
    days_late: null,
    thumbnail_url: null,
    ...overrides,
  }
}

describe('external work groups', () => {
  it('counts a week as today and the six days after it', () => {
    const summary = summarizeExternalWork(
      [
        row({ latest_pickup_date: '2026-11-10' }),
        row({ latest_pickup_date: '2026-11-16' }),
        row({ latest_pickup_date: '2026-11-17' }),
      ],
      '2026-11-10',
    )

    expect(summary).toEqual({ today: 1, week: 2, critical: 0 })
  })

  it('orders the lanes by their next send-out and marks a lane of suggestions', () => {
    const lanes = groupExternalWorkBySupplier([
      row({ supplier_name: 'Coater', latest_pickup_date: '2026-11-14' }),
      row({ supplier_name: 'Hardener', latest_pickup_date: '2026-11-12', ready_now: true }),
      row({ supplier_name: 'Hardener', latest_pickup_date: '2026-11-11', supplier_suggested: false }),
      row({ supplier_name: null, latest_pickup_date: '2026-11-20' }),
    ])

    expect(lanes.map((lane) => [lane.supplier, lane.nextLatestPickup, lane.ready, lane.suggested])).toEqual([
      ['Hardener', '2026-11-11', 1, false],
      ['Coater', '2026-11-14', 0, true],
      [null, '2026-11-20', 0, true],
    ])
  })
})
