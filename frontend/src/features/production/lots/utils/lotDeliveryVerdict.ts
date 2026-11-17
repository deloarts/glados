import { DAY_MS, formatISODate, toDayKey } from '@/core/utils/dates'

import type { LotStateSignal } from './lotStateSummary'
import type { LotPositionResponse, LotResponse } from '../../types/productionLotsResponse'
import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'

export interface LotDeliveryVerdictInput {
  lot: LotResponse
  productionOrders: ProductionOrderResponse[]
  // Actual delivery instant per external or mixed position.
  externalDeliveryDates?: Record<number, string | null>
  // The lot_completed event timestamp, the fallback when no order date exists.
  completedAt?: string | null
  // Injected so the function stays pure.
  today: string
}

// Both operands are day keys, so the difference is an exact number of days.
function dayKeyToUTC(key: string): number {
  const [y, m, d] = key.split('-').map(Number)
  return Date.UTC(y ?? 0, (m ?? 1) - 1, d ?? 1)
}

function dayDiff(laterKey: string, earlierKey: string): number {
  return (dayKeyToUTC(laterKey) - dayKeyToUTC(earlierKey)) / DAY_MS
}

type Contribution =
  | { kind: 'excluded' } // canceled position/order: contributes nothing, no penalty
  | { kind: 'unknown' } // live but no date yet: degrades the verdict to "due"
  | { kind: 'known'; dayKey: string }

function orderContribution(order: ProductionOrderResponse): Contribution {
  if (order.status === 'canceled') return { kind: 'excluded' }
  // A finished order contributes its actual_end, not a stale planned_end.
  const source =
    order.status === 'completed' ? (order.actual_end ?? order.planned_end) : order.planned_end
  return source ? { kind: 'known', dayKey: toDayKey(source) } : { kind: 'unknown' }
}

function externalContribution(
  position: LotPositionResponse,
  externalDeliveryDates: Record<number, string | null>,
): Contribution {
  const delivered = externalDeliveryDates[position.id]
  if (delivered) return { kind: 'known', dayKey: toDayKey(delivered) }
  return position.expected_delivery_date
    ? { kind: 'known', dayKey: toDayKey(position.expected_delivery_date) }
    : { kind: 'unknown' }
}

// A position's latest date across its external and internal legs.
function positionContributions(
  position: LotPositionResponse,
  ordersByPosition: Map<number, ProductionOrderResponse[]>,
  externalDeliveryDates: Record<number, string | null>,
): Contribution[] {
  if (position.status === 'canceled') return [{ kind: 'excluded' }]
  if (position.kind === 'unassigned') return [{ kind: 'unknown' }]

  const contributions: Contribution[] = []
  if (position.kind === 'external' || position.kind === 'mixed') {
    contributions.push(externalContribution(position, externalDeliveryDates))
  }
  if (position.kind === 'internal' || position.kind === 'mixed') {
    const liveOrders = (ordersByPosition.get(position.id) ?? []).filter(
      (o) => o.status !== 'canceled',
    )
    if (liveOrders.length === 0) contributions.push({ kind: 'unknown' })
    else contributions.push(...liveOrders.map(orderContribution))
  }
  return contributions
}

// The latest actual_end or delivery_date, falling back to the lot_completed
// event. Force completion sets both dates on every live order and item, so
// only a lot with no assigned positions reaches the fallback.
function completionDayKey(
  lot: LotResponse,
  productionOrders: ProductionOrderResponse[],
  externalDeliveryDates: Record<number, string | null>,
  completedAt: string | null,
): string | null {
  const dayKeys: string[] = []
  for (const order of productionOrders) {
    if (order.status === 'canceled') continue
    if (order.actual_end) dayKeys.push(toDayKey(order.actual_end))
  }
  for (const position of lot.positions ?? []) {
    if (position.status === 'canceled') continue
    if (position.kind !== 'external' && position.kind !== 'mixed') continue
    const delivered = externalDeliveryDates[position.id]
    if (delivered) dayKeys.push(toDayKey(delivered))
  }
  if (dayKeys.length > 0) return dayKeys.reduce((latest, key) => (key > latest ? key : latest))
  return completedAt ? toDayKey(completedAt) : null
}

/**
 * The lot's delivery timeliness as one chip, or null without a required
 * delivery date or for a canceled lot.
 */
export function buildLotDeliveryVerdict(input: LotDeliveryVerdictInput): LotStateSignal | null {
  const { lot, productionOrders, externalDeliveryDates = {}, completedAt = null, today } = input

  if (!lot.required_delivery_date || lot.status === 'canceled') return null
  const requiredKey = lot.required_delivery_date

  if (lot.status === 'completed') {
    const completionKey = completionDayKey(
      lot,
      productionOrders,
      externalDeliveryDates,
      completedAt,
    )
    if (!completionKey) return null
    if (completionKey > requiredKey) {
      return {
        id: 'deliveryCompletedLate',
        labelKey: 'production.lots.detail.state.deliveryCompletedLate',
        severity: 'danger',
        icon: 'mdi mdi-alert',
        tooltipKey: 'production.lots.detail.state.deliveryCompletedLateTooltip',
        tooltipParams: { count: dayDiff(completionKey, requiredKey) },
      }
    }
    return {
      id: 'deliveryCompletedOnTime',
      labelKey: 'production.lots.detail.state.deliveryCompletedOnTime',
      severity: 'success',
      icon: 'mdi mdi-check-circle-outline',
    }
  }

  if (requiredKey < today) {
    return {
      id: 'deliveryLate',
      labelKey: 'production.lots.detail.state.deliveryLate',
      severity: 'danger',
      icon: 'mdi mdi-alert',
      tooltipKey: 'production.lots.detail.state.deliveryLateTooltip',
      tooltipParams: { count: dayDiff(today, requiredKey) },
    }
  }

  const ordersByPosition = new Map<number, ProductionOrderResponse[]>()
  for (const order of productionOrders) {
    const list = ordersByPosition.get(order.lot_position_id) ?? []
    list.push(order)
    ordersByPosition.set(order.lot_position_id, list)
  }

  let coverageComplete = true
  let forecastKey: string | null = null
  for (const position of lot.positions ?? []) {
    for (const contribution of positionContributions(
      position,
      ordersByPosition,
      externalDeliveryDates,
    )) {
      if (contribution.kind === 'excluded') continue
      if (contribution.kind === 'unknown') {
        coverageComplete = false
        continue
      }
      if (!forecastKey || contribution.dayKey > forecastKey) forecastKey = contribution.dayKey
    }
  }

  // Unassigned or unscheduled positions have no date, so claiming "On track"
  // would be unfounded. "Due {date}" admits the gap without implying trouble.
  if (!coverageComplete) {
    return {
      id: 'deliveryDue',
      labelKey: 'production.lots.detail.state.deliveryDue',
      labelParams: { date: formatISODate(requiredKey) },
      severity: 'info',
      icon: 'mdi mdi-calendar-clock-outline',
    }
  }

  if (forecastKey && forecastKey > requiredKey) {
    return {
      id: 'deliveryWillBeLate',
      labelKey: 'production.lots.detail.state.deliveryWillBeLate',
      labelParams: { date: formatISODate(forecastKey) },
      severity: 'warn',
      icon: 'mdi mdi-alert',
      tooltipKey: 'production.lots.detail.state.deliveryWillBeLateTooltip',
      tooltipParams: { count: dayDiff(forecastKey, requiredKey) },
    }
  }

  return {
    id: 'deliveryOnTrack',
    labelKey: 'production.lots.detail.state.deliveryOnTrack',
    labelParams: { date: formatISODate(requiredKey) },
    severity: 'success',
    icon: 'mdi mdi-check-circle-outline',
  }
}
