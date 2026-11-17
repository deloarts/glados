import type { MadeItemResponse } from '@/features/made-items'
import type { Schemas } from '@/core/api/generated'
import type { ProductionOrderResponse } from './productionOrdersResponse'
import type { LocalizedText } from '@/shared/utils/localizedText'

export type LotStatus = Schemas['LotStatus']
export type LotPositionKind = Schemas['LotPositionKind']
export type LotPositionStatus = Schemas['LotPositionStatus']
export type LotPriority = Schemas['UrgencyClass']
export type ProductionOrderStatus = Schemas['ProductionOrderStatus']
export type SourceApprovalStatus = Schemas['SourceApprovalStatus']

// The full production order is on the wire; widen this pick when a field
// is needed instead of fetching orders separately.
export type LotPositionProductionOrderSummary = Pick<
  ProductionOrderResponse,
  | 'id'
  | 'production_order_number'
  | 'status'
  | 'priority'
  | 'quantity'
  | 'quantity_completed'
  | 'machine_id'
  | 'machine_internal_name'
  // machine_pool_id without machine_id means pool-assigned but not yet
  // resolved to a machine.
  | 'machine_pool_id'
  | 'machine_pool_name'
  | 'conflicts'
  // Sent back with a planned-date edit of the order from the lot.
  | 'edit_version'
>

// Flattened for the lots list, with planned_by reduced to a name.
export type LotSummaryProductionOrderResponse = Schemas['LotSummaryProductionOrderResponse']

// A lots-list position with the order item's delivery and pickup facts
// inlined, so no follow-up fetch is needed.
export type LotSummaryPositionResponse = Schemas['LotSummaryPositionResponse']

// A step either has a fabrication method or an inspection method, never both.
export type StepRole = Schemas['StepRole']

type LotStepBaseResponse = Omit<
  Schemas['LotStepResponse'],
  'role' | 'fabrication_method_id' | 'inspection_method_id' | 'inspection_method_name' | 'inspection_method_requires_evidence'
>

export interface FabricationLotStep extends LotStepBaseResponse {
  role: 'fabrication'
  fabrication_method_id: number
  inspection_method_id: null
  inspection_method_name: null
  inspection_method_requires_evidence: null
}

export interface InspectionLotStep extends LotStepBaseResponse {
  role: 'inspection'
  fabrication_method_id: null
  fabrication_method_requires_machine: false
  inspection_method_id: number
  inspection_method_name: LocalizedText
  // Requires a measurement report upload at completion.
  inspection_method_requires_evidence: boolean
}

export type LotStepResponse = FabricationLotStep | InspectionLotStep

// Lets the lots list decide step clickability without a full-lot fetch.
// An internal position can be committed without a machine. `actions` are the
// actions the step's position offers.
export type LotSummaryStepExtra = Pick<
  Schemas['LotSummaryStepResponse'],
  | 'position_kind'
  | 'position_needs_machine'
  | 'position_status'
  | 'position_quantity'
  | 'position_quantity_remaining'
  | 'actions'
>

export type LotSummaryStepResponse =
  | (FabricationLotStep & LotSummaryStepExtra)
  | (InspectionLotStep & LotSummaryStepExtra)

// steps uses the role union and production_orders the summary pick.
export type LotPositionResponse = Omit<
  Schemas['LotPositionResponse'],
  'steps' | 'production_orders'
> & {
  steps: LotStepResponse[]
  production_orders: LotPositionProductionOrderSummary[]
}

export type LotOriginDisposition = Schemas['LotOriginDisposition']

export type FollowUpLotResponse = Schemas['FollowUpLotResponse']

// positions and steps use the role union. quantity_scrapped and
// replacement_lot_ids are optional although the schema marks them required;
// callers read them with a fallback.
export type LotResponse = Omit<
  Schemas['LotResponse'],
  'positions' | 'steps' | 'quantity_scrapped' | 'replacement_lot_ids'
> & {
  positions: LotPositionResponse[]
  steps: LotStepResponse[]
  quantity_scrapped?: number
  replacement_lot_ids?: number[]
}

export type LotSummaryResponse = Omit<
  Schemas['LotSummaryResponse'],
  'steps' | 'quantity_scrapped' | 'replacement_lot_ids'
> & {
  steps: LotSummaryStepResponse[]
  quantity_scrapped?: number
  replacement_lot_ids?: number[]
}

// Response of both the order scrap and the lot scrap endpoints.
export type ScrapPiecesResponse = Omit<Schemas['ScrapPiecesResponse'], 'lot'> & {
  lot: LotSummaryResponse
}

export type LotPositionCompletionResponse = Schemas['LotPositionCompletionResponse']

export type LotMaterialReceiptResponse = Schemas['LotMaterialReceiptResponse']

export type LotPositionBalanceResponse = Schemas['LotPositionBalanceResponse']

export type LotPositionProvisionResponse = Schemas['LotPositionProvisionResponse']

// Audit trail with one row per lot, position, step or order mutation.
// entity_id is not a foreign key, it must keep resolving after the row is
// deleted.
export type LotEventResponse = Schemas['LotEventResponse']

export type LotEventEntity = LotEventResponse['entity']

export type LotEventType = Schemas['LotEventType']

// A demand this lot covers, plus how much of it this lot allocates.
// item uses MadeItemResponse, whose processes are refined to the role union.
export type LotDemandResponse = Omit<Schemas['LotDemandResponse'], 'item'> & {
  item: MadeItemResponse | null
}

export type AutoAssignLotGroupDemandResponse = Schemas['AutoAssignLotGroupDemandResponse']

export type AutoAssignLotGroupResponse = Schemas['AutoAssignLotGroupResponse']
