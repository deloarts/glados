import { describe, it, expect } from 'vitest'

import {
  canDemandSourceItem,
  canSwitchMaterialSource,
  isSourceApprovalPending,
  isSourceApprovalRejected,
} from '../lotSourceEligibility'
import { makeLot } from '../../__tests__/fixtures'

import type { LotSummaryResponse, SourceApprovalStatus } from '../../../types/productionLotsResponse'

const ALL_STATUSES: SourceApprovalStatus[] = ['not_required', 'pending', 'approved', 'rejected']

// canSwitchMaterialSource takes a LotSummaryResponse, structurally distinct
// from the LotResponse the shared `makeLot` fixture builds (different
// positions/steps element types), so it can't be passed there directly.
// Only input_demand_id/demand_status matter to this function, so reusing
// makeLot's other fields via a cast is safer than hand-rolling a second,
// possibly-divergent fixture.
// A lot that is not finished, on which the server offers the switch.
function asSummaryLot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return {
    ...makeLot([]),
    demand_status: 'open',
    actions: ['switch_source'],
    ...overrides,
  } as unknown as LotSummaryResponse
}

describe('isSourceApprovalPending', () => {
  it.each(ALL_STATUSES)('is true only for the pending status (checking %s)', (status) => {
    expect(isSourceApprovalPending({ source_approval_status: status })).toBe(status === 'pending')
  })
})

describe('isSourceApprovalRejected', () => {
  it.each(ALL_STATUSES)('is true only for the rejected status (checking %s)', (status) => {
    expect(isSourceApprovalRejected({ source_approval_status: status })).toBe(status === 'rejected')
  })
})

// Mirrors the backend guard in create_source_item_demand.py: pending or
// rejected must block the "Demand Source Item" action even when the lot
// otherwise has everything it needs (a source item, no demand yet).
describe('canDemandSourceItem', () => {
  it('is false while pending, even with a source item and no demand yet', () => {
    expect(
      canDemandSourceItem({
        source_bought_item_id: null,
        source_item_id: 5,
        input_demand_id: null,
        source_approval_status: 'pending',
      }),
    ).toBe(false)
  })

  it('is false while rejected, even with a source item and no demand yet', () => {
    expect(
      canDemandSourceItem({
        source_bought_item_id: null,
        source_item_id: 5,
        input_demand_id: null,
        source_approval_status: 'rejected',
      }),
    ).toBe(false)
  })

  it('is true for not_required with a source item and no demand', () => {
    expect(
      canDemandSourceItem({
        source_bought_item_id: null,
        source_item_id: 5,
        input_demand_id: null,
        source_approval_status: 'not_required',
      }),
    ).toBe(true)
  })

  // cancel_source_item_demand.py clears input_demand_id but leaves the
  // approval decision itself as historical fact (status stays 'approved',
  // not reset to 'pending'), so a re-demand after a cancel needs no second
  // approval.
  it('is true for approved with input_demand_id null - approval survives a demand cancel', () => {
    expect(
      canDemandSourceItem({
        source_bought_item_id: null,
        source_item_id: 5,
        input_demand_id: null,
        source_approval_status: 'approved',
      }),
    ).toBe(true)
  })

  it('is false once a demand already exists, regardless of approval status', () => {
    expect(
      canDemandSourceItem({
        source_bought_item_id: null,
        source_item_id: 5,
        input_demand_id: 99,
        source_approval_status: 'approved',
      }),
    ).toBe(false)
  })

  it('is false with neither a bought nor a source item, even when not_required', () => {
    expect(
      canDemandSourceItem({
        source_bought_item_id: null,
        source_item_id: null,
        input_demand_id: null,
        source_approval_status: 'not_required',
      }),
    ).toBe(false)
  })
})

// canSwitchMaterialSource is the pinned escape hatch out of a stuck pending
// (or rejected) lot: switching the source re-derives the approval status
// from scratch (switch_lot_material_source.py), so the switch button itself
// must stay available regardless of the current approval status; it only
// ever gates on whether a demand is already linked and, if so, still open.
describe('canSwitchMaterialSource', () => {
  it('is not switchable on a lot the server offers no switch on, a finished one', () => {
    expect(
      canSwitchMaterialSource(
        asSummaryLot({ status: 'canceled', source_approval_status: 'pending', input_demand_id: null, actions: [] }),
      ),
    ).toBe(false)
  })

  it('is switchable for a pending lot with no demand yet', () => {
    expect(
      canSwitchMaterialSource(
        asSummaryLot({ source_approval_status: 'pending', input_demand_id: null }),
      ),
    ).toBe(true)
  })

  it('is switchable for a rejected lot with no demand yet', () => {
    expect(
      canSwitchMaterialSource(
        asSummaryLot({ source_approval_status: 'rejected', input_demand_id: null }),
      ),
    ).toBe(true)
  })

  it('still gates on input_demand_id/demand_status once a demand exists, independent of approval status', () => {
    expect(
      canSwitchMaterialSource(
        asSummaryLot({
          source_approval_status: 'approved',
          input_demand_id: 5,
          demand_status: 'open',
        }),
      ),
    ).toBe(true)
    expect(
      canSwitchMaterialSource(
        asSummaryLot({
          source_approval_status: 'approved',
          input_demand_id: 5,
          demand_status: 'fulfilled',
        }),
      ),
    ).toBe(false)
  })
})
