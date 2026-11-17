import { conflictLabelKey, conflictSeverity, conflictTooltipKey } from '../../utils/productionOrderConflicts'
import { buildLotDeliveryVerdict } from './lotDeliveryVerdict'

import type { LotResponse } from '../../types/productionLotsResponse'
import type { ProductionOrderResponse, ScheduleConflict } from '../../types/productionOrdersResponse'
import type { SourceItemDemandResponse } from '@/features/source-items'

export interface LotStateSignal {
  id: string
  labelKey: string
  labelParams?: Record<string, unknown>
  tooltipKey?: string
  tooltipParams?: Record<string, unknown>
  severity: string
  icon: string
}

export interface LotStateSummaryInput {
  lot: LotResponse
  productionOrders: ProductionOrderResponse[]
  sourceItemDemand: SourceItemDemandResponse | null
  sourceItemDemandArrived: number
  // Forwarded to buildLotDeliveryVerdict.
  externalDeliveryDates?: Record<number, string | null>
  completedAt?: string | null
  // Injected so the function stays pure.
  today: string
}

// Informational conflicts that never surface as a blocker.
const INFORMATIONAL_CONFLICTS = new Set<ScheduleConflict>([
  'estimate_from_time_budget',
  'waiting_on_predecessor',
])

// What the lot is waiting on, for the record header. Terminal and on-hold
// statuses short-circuit, since that single fact is the whole answer.
export function buildLotStateSummary(input: LotStateSummaryInput): LotStateSignal[] {
  const {
    lot,
    productionOrders,
    sourceItemDemand,
    sourceItemDemandArrived,
    externalDeliveryDates,
    completedAt,
    today,
  } = input

  if (lot.status === 'completed') {
    const completedChip: LotStateSignal = {
      id: 'completed',
      labelKey: 'production.lots.detail.state.completed',
      severity: 'success',
      icon: 'mdi mdi-check-circle-outline',
    }
    const verdict = buildLotDeliveryVerdict({
      lot,
      productionOrders,
      externalDeliveryDates,
      completedAt,
      today,
    })
    return verdict ? [completedChip, verdict] : [completedChip]
  }
  if (lot.status === 'canceled') {
    return [
      {
        id: 'canceled',
        labelKey: 'production.lots.detail.state.canceled',
        severity: 'danger',
        icon: 'mdi mdi-close-circle-outline',
      },
    ]
  }
  // Terminal, but never counts as delivered.
  if (lot.status === 'scrapped') {
    return [
      {
        id: 'scrapped',
        labelKey: 'production.lots.detail.state.scrapped',
        severity: 'danger',
        icon: 'mdi mdi-delete-alert-outline',
      },
    ]
  }
  if (lot.status === 'on_hold') {
    return [
      {
        id: 'onHold',
        labelKey: 'production.lots.detail.state.onHold',
        severity: 'danger',
        icon: 'mdi mdi-pause-circle-outline',
      },
    ]
  }

  // Blockers only, so the fallback below can test them without the verdict.
  const blockers: LotStateSignal[] = []
  const activeOrders = productionOrders.filter((o) => o.status !== 'canceled')

  const verdict = buildLotDeliveryVerdict({
    lot,
    productionOrders,
    externalDeliveryDates,
    completedAt,
    today,
  })

  // The backend only flags sequence 1 orders, so a lot with a demand but no
  // order yet needs its own fallback.
  const waitingOnOrder = activeOrders.some((o) => o.waiting_on_raw_material)
  const waitingOnDemandFallback =
    !waitingOnOrder &&
    activeOrders.length === 0 &&
    !!lot.input_demand_id &&
    !!sourceItemDemand &&
    sourceItemDemandArrived < sourceItemDemand.quantity
  if (waitingOnOrder || waitingOnDemandFallback) {
    blockers.push({
      id: 'waitingOnMaterial',
      labelKey: 'production.lots.detail.state.waitingOnMaterial',
      severity: 'warn',
      icon: 'mdi mdi-alert',
      tooltipKey: 'production.lots.detail.rawMaterial.noneArrivedTooltip',
    })
  } else if (
    !lot.source_bought_item_id &&
    !lot.source_item_id &&
    !lot.source_made_item_id &&
    !lot.input_demand_id &&
    !lot.is_alteration
  ) {
    blockers.push({
      id: 'noMaterialSource',
      labelKey: 'production.lots.detail.state.noMaterialSource',
      severity: 'warn',
      icon: 'mdi mdi-alert-circle-outline',
    })
  }

  // Every other position is done but the inspection position is not, so the
  // lot only waits for QA sign-off.
  const inspectionPositions = (lot.positions ?? []).filter((p) =>
    (p.steps ?? []).some((s) => s.role === 'inspection'),
  )
  const nonInspectionPositions = (lot.positions ?? []).filter((p) =>
    (p.steps ?? []).every((s) => s.role !== 'inspection'),
  )
  const awaitingQa =
    inspectionPositions.some((p) => p.status !== 'completed') &&
    nonInspectionPositions.every((p) => p.status === 'completed')
  if (awaitingQa) {
    blockers.push({
      id: 'awaitingQa',
      labelKey: 'production.lots.detail.state.awaitingQa',
      tooltipKey: 'production.lots.detail.state.awaitingQaTooltip',
      severity: 'warn',
      icon: 'mdi mdi-check-decagram',
    })
  }

  const unassignedCount = (lot.positions ?? []).filter((p) => p.kind === 'unassigned').length
  if (unassignedCount > 0) {
    blockers.push({
      id: 'notPlanned',
      labelKey: 'production.lots.detail.state.notPlanned',
      labelParams: { count: unassignedCount },
      severity: 'warn',
      icon: 'mdi mdi-calendar-remove-outline',
    })
  }

  const waitingOnSupplier = (lot.positions ?? []).some(
    (p) => (p.kind === 'external' || p.kind === 'mixed') && p.status === 'ordered_or_queued',
  )
  if (waitingOnSupplier) {
    blockers.push({
      id: 'waitingOnSupplier',
      labelKey: 'production.lots.detail.state.waitingOnSupplier',
      severity: 'info',
      icon: 'mdi mdi-truck-outline',
    })
  }

  const conflicts = new Set<ScheduleConflict>()
  for (const order of activeOrders) {
    for (const conflict of order.conflicts ?? []) {
      if (INFORMATIONAL_CONFLICTS.has(conflict)) continue
      // The delivery verdict already reports past_target_date when the lot has a
      // required date; without one the verdict is null and the chip stays.
      if (
        conflict === 'past_target_date' &&
        (verdict?.id === 'deliveryLate' || verdict?.id === 'deliveryWillBeLate')
      )
        continue
      conflicts.add(conflict)
    }
  }
  for (const conflict of conflicts) {
    blockers.push({
      id: `conflict-${conflict}`,
      labelKey: conflictLabelKey(conflict),
      tooltipKey: conflictTooltipKey(conflict),
      severity: conflictSeverity[conflict],
      icon: 'mdi mdi-alert',
    })
  }

  // Tested against the blockers alone, since the verdict chip must not hide
  // the "In progress" chip.
  if (blockers.length === 0) {
    const inProgress = activeOrders.some((o) => o.status === 'in_progress')
    blockers.push(
      inProgress
        ? {
            id: 'inProgress',
            labelKey: 'production.lots.detail.state.inProgress',
            severity: 'warn',
            icon: 'mdi mdi-progress-wrench',
          }
        : {
            id: 'onTrack',
            labelKey: 'production.lots.detail.state.onTrack',
            severity: 'success',
            icon: 'mdi mdi-check-circle-outline',
          },
    )
  }

  return verdict ? [verdict, ...blockers] : blockers
}
