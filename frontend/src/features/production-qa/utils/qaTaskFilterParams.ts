import { dateToParam } from '@/core/utils/dates'

import type { QaSortBy, QaSortDir } from '../stores/qaFiltersStore'
import type { ProductionOrderStatus } from '@/features/production'
import type { QaTaskFilterParams } from '../types/qaTaskResponse'

/** The filter values the request is built from. */
export interface QaTaskFilterState {
  search: string
  showCompleted: boolean
  showCanceled: boolean
  showFuture: boolean
  statuses: ProductionOrderStatus[]
  inspectionMethodIds: number[]
  lotNumber: string
  projectNumber: string
  itemText: string
  quantityMin: number | null
  quantityMax: number | null
  plannedStartFrom: Date | null
  plannedStartTo: Date | null
  finishedFrom: Date | null
  finishedTo: Date | null
  finishedByIds: number[]
  sortBy: QaSortBy | null
  sortDir: QaSortDir
}

/**
 * Maps the filters onto GET /production-qa params, leaving empty fields
 * out.
 */
export function buildQaTaskFilterParams(
  filters: QaTaskFilterState,
  page?: { skip: number; limit: number },
): QaTaskFilterParams {
  const date = (value: Date | null) => dateToParam(value) ?? undefined
  return {
    include_completed: filters.showCompleted,
    include_canceled: filters.showCanceled,
    include_future: filters.showFuture,
    ...(filters.search ? { search: filters.search } : {}),
    ...(filters.statuses.length > 0 ? { status: filters.statuses } : {}),
    ...(filters.inspectionMethodIds.length > 0
      ? { inspection_method_id: filters.inspectionMethodIds }
      : {}),
    ...(filters.lotNumber ? { lot_number: filters.lotNumber } : {}),
    ...(filters.projectNumber ? { project_number: filters.projectNumber } : {}),
    ...(filters.itemText ? { item_text: filters.itemText } : {}),
    ...(filters.quantityMin !== null ? { quantity_min: filters.quantityMin } : {}),
    ...(filters.quantityMax !== null ? { quantity_max: filters.quantityMax } : {}),
    ...(filters.plannedStartFrom ? { planned_start_from: date(filters.plannedStartFrom) } : {}),
    ...(filters.plannedStartTo ? { planned_start_to: date(filters.plannedStartTo) } : {}),
    ...(filters.finishedFrom ? { finished_from: date(filters.finishedFrom) } : {}),
    ...(filters.finishedTo ? { finished_to: date(filters.finishedTo) } : {}),
    ...(filters.finishedByIds.length > 0 ? { finished_by_id: filters.finishedByIds } : {}),
    ...(filters.sortBy ? { order_by: filters.sortBy, order_dir: filters.sortDir } : {}),
    ...(page ? { skip: page.skip, limit: page.limit } : {}),
  }
}
