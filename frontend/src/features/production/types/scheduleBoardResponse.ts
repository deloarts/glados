import type { Schemas } from '@/core/api/generated'

export type ScheduleBoardOrderResponse = Schemas['ScheduleBoardOrderResponse']

export type MachineCapacityDayResponse = Schemas['MachineCapacityDayResponse']

export type ScheduleBoardMachineResponse = Schemas['ScheduleBoardMachineResponse']

// Summed across the pool's members. Their figures already include floating
// pool orders, so this is committed plus provisional load.
export type ScheduleBoardPoolResult = Schemas['ScheduleBoardPoolResponse']

export type ScheduleBoardResponse = Schemas['ScheduleBoardResponse']

// 'machines' resolves pool orders to a member machine. 'pools' never writes
// machine_id; the shop floor picks the machine when starting. See
// docs/reference/scheduling.md.
export type AutoPlanPlanningLevel = Schemas['AutoPlanRequest']['planning_level']

export type AutoPlanAlgorithm =
  | 'urgent_first'
  | 'strict_deadline'
  | 'fair_queue'
  | 'balanced_load'
  | 'critical_ratio'
  | 'shortest_processing_time'

// The backend takes any string and falls back to the default algorithm for
// an unknown one, so the request narrows it to the algorithms the UI offers.
export type AutoPlanRequest = Omit<Schemas['AutoPlanRequest'], 'algorithm'> & {
  algorithm: AutoPlanAlgorithm
}

export type AutoPlanOrderDiffResponse = Schemas['AutoPlanOrderDiffResponse']

// An order the planner could not place at all, unlike ScheduleConflict.
// The label helpers fall back to a generic label for unknown reasons.
export type AutoPlanSkipReason = Schemas['AutoPlanSkipReason']

export type AutoPlanSkippedOrderResponse = Schemas['AutoPlanSkippedOrderResponse']

export type AutoPlanResponse = Schemas['AutoPlanResponse']

// Hand-written, since the SSE progress event has no OpenAPI schema.
// eslint-disable-next-line no-restricted-syntax -- the SSE progress event has no OpenAPI schema
export interface AutoPlanProgressOrder {
  order_id: number
  production_order_number: string
  lot_number: string
  made_item_part_number: string
  placed: boolean
  before_machine_id: number | null
  after_machine_id: number | null
  before_machine_pool_id: number | null
  after_machine_pool_id: number | null
  // The skip reason of an unplaced order, as in the result's skipped list;
  // null when placed and for a skip the result does not list.
  reason?: string | null
}

export type AutoPlanProgressStage = NonNullable<Schemas['AutoPlanRunResponse']['stage']>

export interface AutoPlanProgressEvent {
  stage: AutoPlanProgressStage
  current: number | null
  total: number | null
  order: AutoPlanProgressOrder | null
}

export type AutoPlanRun = Schemas['AutoPlanRunResponse']

export type AutoPlanRunStatus = Schemas['AutoPlanRunStatusResponse']
