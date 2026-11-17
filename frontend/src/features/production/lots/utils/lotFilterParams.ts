import { dateToParam } from '@/core/utils/dates'
import type { SourceItemDemandStatus } from '@/features/source-items'

import type { LotPriority, LotStatus } from '../../types/productionLotsResponse'
import type {
  LotCoverageFilter,
  LotFilterParams,
  LotStepMethodFilter,
  StepDisplayStatus,
} from '../../types/productionLotsRequest'

// Builds the filter half of a GET /production-lots request from the filters
// store and the Manage panel state. Paging and sort are added by callers.

// Lot-level, combinable with the position-level smart filter.
const NEEDS_ASSIGNMENT_STATUSES: LotStatus[] = ['draft', 'partially_planned']

// The filters store satisfies this structurally.
export interface LotFilterFieldValues {
  search: string
  projectNumber: string
  itemArticleName: string
  itemPartNumber: string
  statusFilter: LotStatus | null
  priorityFilter: LotPriority | null
  creatorFilter: number | null
  createdFrom: Date | null
  createdTo: Date | null
  changedByFilter: number | null
  changedFrom: Date | null
  changedTo: Date | null
  needsAssignmentOnly: boolean
  needsApprovalOnly: boolean
  lotNumber: string
  targetDateFrom: Date | null
  targetDateTo: Date | null
  quantityMin: number | null
  quantityMax: number | null
  sourceText: string
  sourceDimension: string
  sourceType: string
  sourceStatus: SourceItemDemandStatus | null
  sourceDeliveryFrom: Date | null
  sourceDeliveryTo: Date | null
  stepMethod: string | null
  stepStatus: StepDisplayStatus | null
  stepSetupMin: number | null
  stepSetupMax: number | null
  stepPerPieceMin: number | null
  stepPerPieceMax: number | null
  stepPlannedStartFrom: Date | null
  stepPlannedStartTo: Date | null
  stepPlannedEndFrom: Date | null
  stepPlannedEndTo: Date | null
  stepDeliveryFrom: Date | null
  stepDeliveryTo: Date | null
  stepNote: string
}

// Each open Manage panel sends its actionable_for value while the smart
// filter is on; Manage Production also narrows to its target's coverage.
export interface LotFilterContext {
  smartFilterEnabled: boolean
  showManageOrders: boolean
  showManageProduction: boolean
  showManageSource: boolean
  coverageFilterArmed: boolean
  selectedMachineId: number | null
  selectedPoolId: number | null
}

// One string for both method families, sent as two exclusive int params.
export function encodeStepMethod(kind: 'fabrication' | 'inspection', id: number): string {
  return `${kind}:${id}`
}

export function decodeStepMethod(value: string | null): LotStepMethodFilter {
  if (!value) return {}
  const [kind, rawId] = value.split(':')
  const id = Number(rawId)
  if (!Number.isInteger(id) || id <= 0) return {}
  if (kind === 'fabrication') return { step_fabrication_method_id: id }
  if (kind === 'inspection') return { step_inspection_method_id: id }
  return {}
}

// Narrows to lots the Manage Production target can cover; off when the
// smart filter is off.
function coverageFilterParams(ctx: LotFilterContext): LotCoverageFilter {
  if (!ctx.coverageFilterArmed || !ctx.smartFilterEnabled) return {}
  if (ctx.selectedMachineId !== null) return { coverable_by_machine_id: ctx.selectedMachineId }
  if (ctx.selectedPoolId !== null) return { coverable_by_pool_id: ctx.selectedPoolId }
  return { coverable_by_any_pool: true }
}

function actionableForParam(ctx: LotFilterContext): Pick<LotFilterParams, 'actionable_for'> {
  if (!ctx.smartFilterEnabled) return {}
  if (ctx.showManageOrders) return { actionable_for: 'orders' }
  if (ctx.showManageProduction) return { actionable_for: 'machines' }
  if (ctx.showManageSource) return { actionable_for: 'source' }
  return {}
}

function text(value: string): string | undefined {
  return value ? value : undefined
}

function day(value: Date | null): string | undefined {
  return dateToParam(value) ?? undefined
}

function num(value: number | null): number | undefined {
  return value ?? undefined
}

export function buildLotFilterParams(
  fields: LotFilterFieldValues,
  ctx: LotFilterContext,
): LotFilterParams {
  const params: LotFilterParams = {
    search: text(fields.search),
    project_number: text(fields.projectNumber),
    item_article_name: text(fields.itemArticleName),
    item_part_number: text(fields.itemPartNumber),
    priority: fields.priorityFilter ?? undefined,
    creator_id: num(fields.creatorFilter),
    created_from: day(fields.createdFrom),
    created_to: day(fields.createdTo),
    changed_by_id: num(fields.changedByFilter),
    changed_from: day(fields.changedFrom),
    changed_to: day(fields.changedTo),
    lot_number: text(fields.lotNumber),
    target_date_from: day(fields.targetDateFrom),
    target_date_to: day(fields.targetDateTo),
    quantity_min: num(fields.quantityMin),
    quantity_max: num(fields.quantityMax),
    source_text: text(fields.sourceText),
    source_dimension: text(fields.sourceDimension),
    source_type: text(fields.sourceType),
    source_status: fields.sourceStatus ?? undefined,
    source_delivery_from: day(fields.sourceDeliveryFrom),
    source_delivery_to: day(fields.sourceDeliveryTo),
    step_status: fields.stepStatus ?? undefined,
    step_setup_min: num(fields.stepSetupMin),
    step_setup_max: num(fields.stepSetupMax),
    step_per_piece_min: num(fields.stepPerPieceMin),
    step_per_piece_max: num(fields.stepPerPieceMax),
    step_planned_start_from: day(fields.stepPlannedStartFrom),
    step_planned_start_to: day(fields.stepPlannedStartTo),
    step_planned_end_from: day(fields.stepPlannedEndFrom),
    step_planned_end_to: day(fields.stepPlannedEndTo),
    step_delivery_from: day(fields.stepDeliveryFrom),
    step_delivery_to: day(fields.stepDeliveryTo),
    step_note: text(fields.stepNote),
    ...(fields.needsAssignmentOnly
      ? { statuses: NEEDS_ASSIGNMENT_STATUSES }
      : fields.statusFilter
        ? { status: fields.statusFilter }
        : {}),
    ...(fields.needsApprovalOnly ? { source_approval_status: 'pending' as const } : {}),
    ...actionableForParam(ctx),
    ...coverageFilterParams(ctx),
    ...decodeStepMethod(fields.stepMethod),
  }
  // Empty fields must be absent, not undefined keys: the request layer
  // serializes the object as query params and callers compare it directly.
  for (const key of Object.keys(params) as (keyof LotFilterParams)[]) {
    if (params[key] === undefined) delete params[key]
  }
  return params
}
