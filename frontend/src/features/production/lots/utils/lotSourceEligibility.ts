import { hasAction } from '@/core/utils/lifecycleActions'

import type {
  LotResponse,
  LotSummaryResponse,
  SourceApprovalStatus,
} from '../../types/productionLotsResponse'

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

export interface SupplierMaterialTag {
  labelKey: string
  tooltipKey: string
  severity: 'info' | 'secondary'
}

const SUPPLIER_MATERIAL_TAGS: Partial<Record<SourceApprovalStatus, SupplierMaterialTag>> = {
  awaiting_first_step: {
    labelKey: 'production.lots.detail.record.sourceApproval.awaitingFirstStep',
    tooltipKey: 'production.lots.detail.record.sourceApproval.awaitingFirstStepTooltip',
    severity: 'info',
  },
  supplier_sourced: {
    labelKey: 'production.lots.detail.record.sourceApproval.supplierSourced',
    tooltipKey: 'production.lots.detail.record.sourceApproval.supplierSourcedTooltip',
    severity: 'secondary',
  },
}

// A lot whose first position goes, or is expected to go, to a supplier needs
// none of our material, which is why it has no demand. Null for any other
// lot.
export function supplierMaterialTag(lot: LotApprovalFields): SupplierMaterialTag | null {
  return SUPPLIER_MATERIAL_TAGS[lot.source_approval_status] ?? null
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
