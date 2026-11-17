import type { Schemas } from '@/core/api/generated'

export type ProductionOrderStatus = Schemas['ProductionOrderStatus']
export type ProductionOrderPriority = Schemas['UrgencyClass']
export type ManufacturingComplexity = Schemas['ComplexityClass']
// Shared by order and lot scrap and the QA completion disposition.
export type ScrapReason = Schemas['ScrapReason']

export type ProductionOrderCompletionResponse = Schemas['ProductionOrderCompletionResponse']

// Rejected-piece disposition, created with an inspection completion whose
// quantity_rejected is above zero.
export type CreatedLotResponse = Schemas['CreatedLotResponse']

// Evidence files attached to an inspection completion.
export type ProductionOrderFileCategory = Schemas['ProductionOrderFileCategory']

export type ProductionOrderFile = Schemas['ProductionOrderFileResponse']

// Informational only, never gates an action.
export type ScheduleConflict = Schemas['ScheduleConflictReason']

export type ManufacturingAssessmentResponse = Schemas['ManufacturingAssessmentResponse']

/**
 * planned_by is null when the scheduler computed the window and set when a
 * person pinned it. started_operator is the operator of the current or last
 * start, overwritten on every start or resume. created_lots is only filled on
 * the response to the completion that created them.
 */
export type ProductionOrderResponse = Schemas['ProductionOrderResponse']
