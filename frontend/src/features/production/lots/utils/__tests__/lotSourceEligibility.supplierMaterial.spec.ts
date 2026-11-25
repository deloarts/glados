import { describe, expect, it } from 'vitest'

import { makeLotSummaryResponse } from '@/test-utils/factories'

import { canDemandSourceItem, supplierMaterialTag } from '../lotSourceEligibility'

describe('supplierMaterialTag', () => {
  it('names a lot awaiting its first step at a supplier', () => {
    const tag = supplierMaterialTag({ source_approval_status: 'awaiting_first_step' })

    expect(tag).toEqual({
      labelKey: 'production.lots.detail.record.sourceApproval.awaitingFirstStep',
      tooltipKey: 'production.lots.detail.record.sourceApproval.awaitingFirstStepTooltip',
      severity: 'info',
    })
  })

  it('names a lot whose material the supplier of its first step brings', () => {
    expect(supplierMaterialTag({ source_approval_status: 'supplier_sourced' })?.labelKey).toBe(
      'production.lots.detail.record.sourceApproval.supplierSourced',
    )
  })

  it('is null for every other status', () => {
    for (const status of ['not_required', 'pending', 'approved', 'rejected'] as const) {
      expect(supplierMaterialTag({ source_approval_status: status })).toBeNull()
    }
  })

  it('still lets a demand be created by hand, for material sent to the supplier', () => {
    const lot = makeLotSummaryResponse({
      source_item_id: 5,
      input_demand_id: null,
      source_approval_status: 'supplier_sourced',
    })

    expect(canDemandSourceItem(lot)).toBe(true)
  })
})
