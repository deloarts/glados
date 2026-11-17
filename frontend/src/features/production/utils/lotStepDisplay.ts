import { dateToParam, parseBackendTimestamp, toLocalDayStart } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { conflictLabelKey } from './productionOrderConflicts'
import { lotPositionStatusKey } from './lotStatus'

import type { PlannedInfo } from '../composables/useLotStepDeliveryInfo'
import type {
  FabricationLotStep,
  InspectionLotStep,
  LotPositionKind,
  LotStepResponse,
  LotSummaryPositionResponse,
  LotSummaryResponse,
  LotSummaryStepResponse,
} from '../types/productionLotsResponse'
import type { Translate } from '@/core/i18n'
import { sortedBySequence } from './sequence'
import { localizeLabel } from '@/shared/utils/localizeLabel'

export type { Translate }

/** The steps of a lot or of one position, in sequence order. */
export function sortedSteps<TStep extends { sequence: number }>(owner: {
  steps?: readonly TStep[] | null
}): TStep[] {
  return sortedBySequence(owner.steps)
}

export function formatMinutesDuration(minutes: number): string {
  if (minutes < 60) {
    const rounded = Math.round(minutes * 10) / 10
    return `${rounded} min`
  }
  if (minutes < 1440) {
    const hours = Math.floor(minutes / 60)
    const remainderMinutes = Math.round(minutes % 60)
    return remainderMinutes > 0 ? `${hours} h ${remainderMinutes} min` : `${hours} h`
  }
  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  const remainderMinutes = Math.round(minutes % 60)
  let result = `${days} d`
  if (hours > 0) result += ` ${hours} h`
  if (remainderMinutes > 0) result += ` ${remainderMinutes} min`
  return result
}

// How long a finished span of work took.
export function formatDurationBetween(startIso: string, endIso: string): string {
  const minutes =
    (parseBackendTimestamp(endIso).getTime() - parseBackendTimestamp(startIso).getTime()) / 60000
  return formatMinutesDuration(Math.max(0, minutes))
}

/**
 * The minutes per piece the backend schedules a step with: its measured
 * estimate, or the project budget share it falls back to until one is
 * measured. Null when the step has neither.
 */
export function stepPerPieceMinutes(step: {
  estimated_minutes_per_piece: number | null
  time_budget_per_piece: number | null
}): number | null {
  return step.estimated_minutes_per_piece ?? step.time_budget_per_piece
}

// Builds the minimal position shape useMachineCapability() needs from the
// lot's flat step list, without fetching the lot.
export function pseudoPosition(
  lot: LotSummaryResponse,
  positionId: number,
): { steps: LotStepResponse[] } {
  return {
    steps: (lot.steps ?? []).filter((s) => s.position_id === positionId),
  }
}

export const STEP_KIND_ICON: Record<LotPositionKind, string | undefined> = {
  unassigned: undefined,
  external: 'mdi-cart',
  internal: 'mdi-factory',
  mixed: 'mdi-swap-horizontal',
}

// Pinned: an inspection step always renders the QA icon, regardless of its
// position kind.
export const INSPECTION_ICON = 'mdi mdi-check-decagram'

export function stepIcon(step: LotSummaryStepResponse): string | undefined {
  if (step.role === 'inspection') return INSPECTION_ICON
  const icon = STEP_KIND_ICON[step.position_kind]
  return icon ? `mdi ${icon}` : undefined
}

// The step's method name, from the inspection method for an inspection
// step. Read method names only through here, so inspection steps always
// render correctly. Spelled out per variant because Pick does not
// distribute over the union.
type MethodNamedStep =
  | Pick<FabricationLotStep, 'role' | 'inspection_method_name' | 'fabrication_method_name'>
  | Pick<InspectionLotStep, 'role' | 'inspection_method_name' | 'fabrication_method_name'>

export function stepMethodLabel(step: MethodNamedStep): string {
  if (step.role === 'inspection') return localizeLabel(step.inspection_method_name)
  return localizeLabel(step.fabrication_method_name)
}

export function stepLabel(step: LotSummaryStepResponse): string {
  const allocated = step.position_quantity - step.position_quantity_remaining
  const method = stepMethodLabel(step)
  if (allocated <= 0 || allocated >= step.position_quantity) return method
  return `${method} (${allocated}/${step.position_quantity})`
}

// Lists the conflicts of a step, without the per-order breakdown.
export function conflictsTooltip(info: PlannedInfo, t: (key: string) => string): string {
  return info.conflicts.map((c) => t(conflictLabelKey(c))).join(', ')
}

// The note under the planned date; conflicts go into the date's tooltip.
export function deliveryNoteLine(info: PlannedInfo): string | null {
  return info.note
}

// The pickup line under the planned date, when a pickup date is set.
export function pickupLine(
  info: PlannedInfo,
  toDateParam: (date: Date) => string | null,
  t: (key: string, params: Record<string, unknown>) => string,
): string | null {
  if (!info.pickup) return null
  const date = toDateParam(info.pickup.date)
  return info.pickup.isReady
    ? t('production.lots.deliveryDate.readyForPickup', { date })
    : t('production.lots.deliveryDate.expectedPickup', { date })
}

// Formats like the date cells, so tooltips match the values they explain.
function formatDateParam(iso: string): string {
  return dateToParam(toLocalDayStart(iso)) ?? iso
}

// Only the reasons that add something beyond the attribution line.
const EARLIEST_START_REASON_KEYS: Record<string, string> = {
  predecessor: 'production.lots.tooltips.earliestStart.predecessor',
  material: 'production.lots.tooltips.earliestStart.material',
  not_before: 'production.lots.tooltips.earliestStart.notBefore',
  queue: 'production.lots.tooltips.earliestStart.queue',
  unknown_chain: 'production.lots.tooltips.earliestStart.unknownChain',
  frozen: 'production.lots.tooltips.earliestStart.frozen',
  missing_material: 'production.lots.tooltips.earliestStart.missingMaterial',
}

// One sentence naming what governs an order's earliest start. A dated
// reason without a date says nothing rather than an incomplete sentence.
function earliestStartTooltip(info: PlannedInfo, t: Translate): string | undefined {
  const { reason, date } = info.earliestStart
  if (!reason) return undefined
  const key = EARLIEST_START_REASON_KEYS[reason]
  if (!key) return undefined
  if (reason === 'unknown_chain' || reason === 'missing_material') return t(key)
  if (!date) return undefined
  return t(key, { date: dateToParam(date) })
}

// Combines every reason the planned date needs explaining: its earliest
// start, being overdue, and conflicts.
export function plannedDateTooltip(info: PlannedInfo, t: Translate): string | undefined {
  const parts: string[] = []
  const earliestStart = earliestStartTooltip(info, t)
  if (earliestStart) parts.push(earliestStart)
  if (info.isOverdue) parts.push(t('production.lots.tooltips.overdue'))
  if (info.conflicts.length > 0) parts.push(conflictsTooltip(info, t))
  return parts.length > 0 ? parts.join('\n') : undefined
}

// The order's machine, else its pool, else nothing.
function machineOrPoolTarget(
  machineName: string | null,
  poolName: string | null,
  t: Translate,
): string {
  if (machineName) return machineName
  if (poolName) return t('production.lots.tooltips.attribution.targetPool', { pool: poolName })
  return t('production.lots.tooltips.attribution.targetNoMachine')
}

const LEAD_DAYS_SOURCE_KEYS: Record<string, string> = {
  supplier: 'production.lots.tooltips.attribution.leadDaysSourceSupplier',
  method: 'production.lots.tooltips.attribution.leadDaysSourceMethod',
  default: 'production.lots.tooltips.attribution.leadDaysSourceDefault',
}

// The lead-time parenthetical inside the forecast sentence, or empty.
function leadDaysNote(days: number | null, source: string | null, t: Translate): string {
  if (days === null || source === null) return ''
  const sourceKey = LEAD_DAYS_SOURCE_KEYS[source]
  if (!sourceKey) return ''
  return t('production.lots.tooltips.attribution.leadDaysNote', { days, source: t(sourceKey) })
}

// One sentence on who or what produced the shown date. It never invents a
// person: a typed external date names the order and its orderer, and a
// forecast or confirmed fact names nobody.
export function plannedAttributionTooltip(info: PlannedInfo, t: Translate): string | undefined {
  const a = info.attribution
  switch (a.kind) {
    case 'external_typed':
      if (!a.orderNumber) return undefined
      return a.personName
        ? t('production.lots.tooltips.attribution.externalTyped', {
            order: a.orderNumber,
            person: a.personName,
          })
        : t('production.lots.tooltips.attribution.externalTypedNoPerson', { order: a.orderNumber })
    case 'external_forecast':
      return t('production.lots.tooltips.attribution.externalForecast', {
        pickup: a.plannedPickupDate ? dateToParam(a.plannedPickupDate) : getEmptyPlaceholder(),
        delivery: a.plannedDeliveryDate ? dateToParam(a.plannedDeliveryDate) : getEmptyPlaceholder(),
        leadDaysNote: leadDaysNote(a.leadDays, a.leadDaysSource, t),
      })
    case 'manual_pinned':
      return a.personName
        ? t('production.lots.tooltips.attribution.manualPinned', { person: a.personName })
        : undefined
    case 'auto_planner':
      return t('production.lots.tooltips.attribution.autoPlanner', {
        target: machineOrPoolTarget(a.machineName, a.poolName, t),
      })
    case 'actual':
      return t('production.lots.tooltips.attribution.actual')
    default:
      return undefined
  }
}

// A sentence with the fact behind the status, or the plain label when the
// summary lacks the data; it never claims data the backend did not send.
export function positionStatusTooltip(
  step: LotSummaryStepResponse,
  position: LotSummaryPositionResponse | undefined,
  t: Translate,
): string {
  const key = lotPositionStatusKey(step.position_status, step.position_kind)
  const plain = t(`production.lots.positionStatus.${key}`)
  switch (key) {
    case 'pending':
      return t('production.lots.tooltips.positionStatus.pending')
    case 'allocated':
      return position?.order_number
        ? t('production.lots.tooltips.positionStatus.allocated', {
            order: position.order_number,
            status: position.order_item_status || plain,
          })
        : plain
    case 'ordered':
      return position?.order_number && position.expected_delivery_date
        ? t('production.lots.tooltips.positionStatus.ordered', {
            order: position.order_number,
            date: formatDateParam(position.expected_delivery_date),
          })
        : plain
    case 'queued': {
      const order = position?.production_orders?.find((po) => po.status !== 'canceled')
      if (!order) return plain
      if (order.machine_internal_name) {
        return t('production.lots.tooltips.positionStatus.queuedOnMachine', {
          machine: order.machine_internal_name,
        })
      }
      if (order.machine_pool_name) {
        return t('production.lots.tooltips.positionStatus.queuedInPool', {
          pool: order.machine_pool_name,
        })
      }
      return t('production.lots.tooltips.positionStatus.queuedNoMachine')
    }
    case 'in_progress': {
      const order = position?.production_orders?.find((po) => po.actual_start)
      return order?.actual_start
        ? t('production.lots.tooltips.positionStatus.inProgress', {
            date: formatDateParam(order.actual_start),
          })
        : plain
    }
    case 'partially_completed': {
      if (position?.order_item_quantity_delivered != null && position.order_item_quantity != null) {
        return t('production.lots.tooltips.positionStatus.partiallyCompleted', {
          done: position.order_item_quantity_delivered,
          qty: position.order_item_quantity,
        })
      }
      // Internal: sum the active orders' completed quantities.
      const done = (position?.production_orders ?? [])
        .filter((po) => po.status !== 'canceled')
        .reduce((sum, po) => sum + po.quantity_completed, 0)
      return done > 0
        ? t('production.lots.tooltips.positionStatus.partiallyCompleted', {
            done,
            qty: step.position_quantity,
          })
        : plain
    }
    case 'completed':
      return t('production.lots.tooltips.positionStatus.completed')
    case 'canceled':
      return t('production.lots.tooltips.positionStatus.canceled')
    default:
      return plain
  }
}

// Who fulfils the step: the supplier order (its number standing in for the
// supplier name) and/or the machine or pool.
export function methodTooltipSuffix(
  position: LotSummaryPositionResponse | undefined,
  t: Translate,
): string | undefined {
  if (!position) return undefined
  const lines: string[] = []
  if ((position.kind === 'external' || position.kind === 'mixed') && position.order_number) {
    lines.push(t('production.lots.tooltips.method.supplierLine', { order: position.order_number }))
  }
  if (position.kind === 'internal' || position.kind === 'mixed') {
    const order = (position.production_orders ?? []).find((po) => po.status !== 'canceled')
    if (order) {
      lines.push(
        t('production.lots.tooltips.method.machineLine', {
          target: machineOrPoolTarget(
            order.machine_internal_name || null,
            order.machine_pool_name || null,
            t,
          ),
        }),
      )
    }
  }
  return lines.length > 0 ? lines.join('\n') : undefined
}

export interface SourceDeliveryInfo {
  date: Date | null
  isFinal: boolean
  orderId: number | null
  orderNumber: string | null
}

// The lot's material delivery from its input demand; null without an
// order behind it.
export function sourceDeliveryInfoFor(lot: LotSummaryResponse): SourceDeliveryInfo | null {
  if (lot.input_demand_id === null) return null
  const orderId = lot.source_order_id ?? null
  const orderNumber = lot.source_order_number ?? null
  if (orderId === null || orderNumber === null) return null
  // A confirmed arrival wins over the projection, matching the backend's
  // own ranking when a demand is split across several orders.
  if (lot.source_delivery_date) {
    return {
      date: toLocalDayStart(lot.source_delivery_date),
      isFinal: true,
      orderId,
      orderNumber,
    }
  }
  if (lot.source_expected_delivery_date) {
    return {
      date: toLocalDayStart(lot.source_expected_delivery_date),
      isFinal: false,
      orderId,
      orderNumber,
    }
  }
  return { date: null, isFinal: false, orderId, orderNumber }
}
