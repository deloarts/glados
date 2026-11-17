import { describe, it, expect } from 'vitest'

import { buildQaTaskFilterParams } from '../qaTaskFilterParams'

import type { QaTaskFilterState } from '../qaTaskFilterParams'

function state(overrides: Partial<QaTaskFilterState> = {}): QaTaskFilterState {
  return {
    search: '',
    showCompleted: false,
    showCanceled: false,
    showFuture: false,
    statuses: [],
    inspectionMethodIds: [],
    lotNumber: '',
    projectNumber: '',
    itemText: '',
    quantityMin: null,
    quantityMax: null,
    plannedStartFrom: null,
    plannedStartTo: null,
    finishedFrom: null,
    finishedTo: null,
    finishedByIds: [],
    sortBy: null,
    sortDir: 'asc',
    ...overrides,
  }
}

describe('buildQaTaskFilterParams', () => {
  it('sends only the three toggles when nothing is filtered', () => {
    expect(buildQaTaskFilterParams(state())).toEqual({
      include_completed: false,
      include_canceled: false,
      include_future: false,
    })
  })

  it('maps every column filter to its query param', () => {
    const params = buildQaTaskFilterParams(
      state({
        statuses: ['queued', 'completed'],
        inspectionMethodIds: [2, 5],
        lotNumber: 'LN-26',
        projectNumber: 'P26',
        itemText: 'Shaft',
        quantityMin: 0,
        quantityMax: 12.5,
        plannedStartFrom: new Date(2026, 8, 1),
        plannedStartTo: new Date(2026, 8, 30),
        finishedFrom: new Date(2026, 7, 3),
        finishedTo: new Date(2026, 7, 4),
        finishedByIds: [9],
      }),
    )
    expect(params).toMatchObject({
      status: ['queued', 'completed'],
      inspection_method_id: [2, 5],
      lot_number: 'LN-26',
      project_number: 'P26',
      item_text: 'Shaft',
      quantity_min: 0,
      quantity_max: 12.5,
      planned_start_from: '2026-09-01',
      planned_start_to: '2026-09-30',
      finished_from: '2026-08-03',
      finished_to: '2026-08-04',
      finished_by_id: [9],
    })
  })

  it('keeps an open-ended range to the bound that is set', () => {
    const params = buildQaTaskFilterParams(state({ plannedStartFrom: new Date(2026, 8, 1) }))
    expect(params.planned_start_from).toBe('2026-09-01')
    expect('planned_start_to' in params).toBe(false)
  })

  it('adds the search, sort and page window alongside the filters', () => {
    const params = buildQaTaskFilterParams(
      state({ search: 'FN-26', sortBy: 'part', sortDir: 'desc', lotNumber: 'LN' }),
      { skip: 25, limit: 25 },
    )
    expect(params).toMatchObject({
      search: 'FN-26',
      order_by: 'part',
      order_dir: 'desc',
      lot_number: 'LN',
      skip: 25,
      limit: 25,
    })
  })
})
