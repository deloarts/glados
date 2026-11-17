import { hasAction } from '@/core/utils/lifecycleActions'

import type { LotResponse, LotSummaryResponse } from '../../types/productionLotsResponse'

type LotSourceFields = Pick<
  LotResponse | LotSummaryResponse,
  'source_bought_item_id' | 'source_item_id' | 'input_demand_id' | 'source_approval_status'
>

type LotApprovalFields = Pick<LotResponse | LotSummaryResponse, 'source_approval_status'>

export function isSourceApprovalPending(lot: LotApprovalFields): boolean {
  return lot.source_approval_status === 'pending'
}

export function isSourceApprovalRejected(lot: LotApprovalFields): boolean {
  return lot.source_approval_status === 'rejected'
}

// A pending or rejected approval must be approved first, as the backend
// enforces.
export function canDemandSourceItem(lot: LotSourceFields): boolean {
  return (
    (lot.source_bought_item_id !== null || lot.source_item_id !== null) &&
    !lot.input_demand_id &&
    !isSourceApprovalPending(lot) &&
    !isSourceApprovalRejected(lot)
  )
}

// The server offers the switch only on a lot that is not finished, and a
// fulfilled raw material demand leaves nothing to switch.
export function canSwitchMaterialSource(lot: LotSummaryResponse): boolean {
  return (
    hasAction(lot, 'switch_source') && (!lot.input_demand_id || lot.demand_status !== 'fulfilled')
  )
}
