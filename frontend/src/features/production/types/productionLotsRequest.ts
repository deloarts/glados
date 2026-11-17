import type { LotPriority, LotStatus } from './productionLotsResponse'
import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type { LotPriority, LotStatus }

export type LotDemandAllocationInput = Schemas['LotDemandAllocationInputRequest']

export type LotCreateRequest = Schemas['LotCreateRequest']

export type LotUpdateRequest = Schemas['LotUpdateRequest']

export type SwitchLotMaterialSourceRequest = Schemas['SwitchLotMaterialSourceRequest']

type LotQuery = QueryOf<'/production-lots'>

// The coverage and step method filters are narrowed below to their mutually
// exclusive combinations.
type LotFilterParamsBase = Omit<
  LotQuery,
  | 'coverable_by_machine_id'
  | 'coverable_by_pool_id'
  | 'coverable_by_any_pool'
  | 'step_fabrication_method_id'
  | 'step_inspection_method_id'
>

export type LotSortBy = NonNullable<LotQuery['order_by']>
export type LotSortDir = NonNullable<LotQuery['order_dir']>

// The step status filter sends the display key so "Pending" never includes
// "Allocated"; the backend maps it back onto status and kind.
export type StepDisplayStatus = NonNullable<LotQuery['step_status']>

// Narrows to lots coverable by one machine, one pool or any pool.
export type LotCoverageFilter =
  | { coverable_by_machine_id: number; coverable_by_pool_id?: never; coverable_by_any_pool?: never }
  | { coverable_by_pool_id: number; coverable_by_machine_id?: never; coverable_by_any_pool?: never }
  | { coverable_by_any_pool: true; coverable_by_machine_id?: never; coverable_by_pool_id?: never }
  | { coverable_by_machine_id?: never; coverable_by_pool_id?: never; coverable_by_any_pool?: never }

// The backend 422s when both ids are sent.
export type LotStepMethodFilter =
  | { step_fabrication_method_id: number; step_inspection_method_id?: never }
  | { step_inspection_method_id: number; step_fabrication_method_id?: never }
  | { step_fabrication_method_id?: never; step_inspection_method_id?: never }

export type LotFilterParams = LotFilterParamsBase & LotCoverageFilter & LotStepMethodFilter

// role defaults to 'fabrication' on the backend.
export type AddLotStepRequest = Omit<Schemas['AddLotStepRequest'], 'role'> & {
  role?: Schemas['StepRole']
}

export type UpdateLotStepRequest = Omit<Schemas['UpdateLotStepRequest'], 'role'> & {
  role?: Schemas['StepRole']
}

export type ReorderLotStepsRequest = Schemas['ReorderLotStepsRequest']

export type RegroupLotPositionsRequest = Schemas['RegroupLotPositionsRequest']

export type AppendLotPositionStepRequest = Omit<
  Schemas['AppendLotPositionStepRequest'],
  'role'
> & {
  role?: Schemas['StepRole']
}

export type AppendLotPositionRequest = Schemas['AppendLotPositionRequest']

export type ReplaceLotStructureStepRequest = Schemas['ReplaceLotStructureStepRequest']

export type ReplaceLotStructurePositionRequest = Schemas['ReplaceLotStructurePositionRequest']

export type ReplaceLotStructureRequest = Schemas['ReplaceLotStructureRequest']

// items_per_unit defaults to 1 on the backend.
export type AssignExternalPositionRequest = Omit<
  Schemas['AssignExternalPositionRequest'],
  'items_per_unit'
> & {
  items_per_unit?: number
}

export type CancelLotRequest = Schemas['CancelLotRequest']

export type CompleteLotRequest = Schemas['CompleteLotRequest']

export type HoldLotRequest = Schemas['HoldLotRequest']

export type RejectLotSourceRequest = Schemas['RejectLotSourceRequest']

export type AssignInternalPositionOrderInput = Schemas['AssignInternalPositionOrderInputRequest']

export type AssignInternalPositionRequest = Schemas['AssignInternalPositionRequest']

export type RecordLotPositionProvisionRequest = Schemas['RecordLotPositionProvisionRequest']

export type ScrapLotPiecesRequest = Schemas['ScrapLotPiecesRequest']
