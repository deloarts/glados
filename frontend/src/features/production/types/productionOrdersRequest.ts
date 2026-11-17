import type { ProductionOrderPriority, ProductionOrderStatus } from './productionOrdersResponse'
import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type { ProductionOrderPriority, ProductionOrderStatus }

export type SplitProductionOrderRequest = Schemas['SplitProductionOrderRequest']

export type MergeProductionOrdersRequest = Schemas['MergeProductionOrdersRequest']

export type ReorderProductionOrdersRequest = Schemas['ReorderProductionOrdersRequest']

// machine_id and machine_pool_id are mutually exclusive (the backend 422s on
// both). Targeting a pool clears machine_id until a machine is picked. The
// union turns sending both into a compile error.
export type ReassignProductionOrderMachineRequest =
  | { machine_id: number | null; machine_pool_id?: never }
  | { machine_pool_id: number | null; machine_id?: never }

// recompute_planned_end defaults to false on the backend.
export type UpdateProductionOrderRequest = Omit<
  Schemas['UpdateProductionOrderRequest'],
  'recompute_planned_end'
> & {
  recompute_planned_end?: boolean
}

export type StartProductionOrderRequest = Schemas['StartProductionOrderRequest']

export type PauseProductionOrderRequest = Schemas['PauseProductionOrderRequest']

export type CancelProductionOrderRequest = Schemas['CancelProductionOrderRequest']

export type ReverseCompletionRequest = Schemas['ReverseCompletionRequest']

/**
 * scrap_reason is optional here, unlike on the scrap endpoint. The
 * quantities default to 0 on the backend.
 */
export type RecordProductionOrderCompletionRequest = Omit<
  Schemas['RecordProductionOrderCompletionRequest'],
  'quantity_rework' | 'quantity_scrap'
> & {
  quantity_rework?: number
  quantity_scrap?: number
}

// Records an internal completion of scrapped pieces and, unless opted out,
// spawns a replacement lot with the same routing.
export type ScrapProductionPiecesRequest = Schemas['ScrapProductionPiecesRequest']

export type RecordManufacturingAssessmentRequest = Schemas['RecordManufacturingAssessmentRequest']

export type ProductionOrderFilterParams = QueryOf<'/production-orders'>
export type ProductionOrderSortBy = NonNullable<ProductionOrderFilterParams['order_by']>
export type ProductionOrderSortDir = NonNullable<ProductionOrderFilterParams['order_dir']>
