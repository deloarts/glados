import { describe, it, expect } from 'vitest'

import { i18n } from '@/core/i18n'
import { dateToParam, toLocalDayStart } from '@/core/utils/dates'
import {
  methodTooltipSuffix,
  plannedAttributionTooltip,
  plannedDateTooltip,
  positionStatusTooltip,
} from '../lotStepDisplay'

import type { PlannedAttribution, PlannedInfo } from '../../composables/useLotStepDeliveryInfo'
import type {
  LotSummaryPositionResponse,
  LotSummaryProductionOrderResponse,
  LotSummaryStepResponse,
} from '../../types/productionLotsResponse'

const t = i18n.global.t as (key: string, params?: Record<string, unknown>) => string

const NO_ATTRIBUTION: PlannedAttribution = {
  kind: null,
  personName: null,
  orderId: null,
  orderNumber: null,
  machineName: null,
  poolName: null,
  plannedPickupDate: null,
  plannedDeliveryDate: null,
  leadDays: null,
  leadDaysSource: null,
}

const NO_EARLIEST_START: PlannedInfo['earliestStart'] = { reason: null, date: null }

function makeAttribution(overrides: Partial<PlannedAttribution> = {}): PlannedAttribution {
  return { ...NO_ATTRIBUTION, ...overrides }
}

function makePlannedInfo(overrides: Partial<PlannedInfo> = {}): PlannedInfo {
  return {
    date: null,
    startDate: null,
    isFinal: false,
    isOverdue: false,
    note: null,
    conflicts: [],
    plannedByLabel: null,
    pickup: null,
    attribution: NO_ATTRIBUTION,
    earliestStart: NO_EARLIEST_START,
    ...overrides,
  }
}

const STEP_BASE = {
  id: 1,
  public_id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
  created: '2026-08-01T09:00:00',
  note: null,
  estimated_setup_minutes: null,
  estimated_minutes_per_piece: null,
  time_budget_per_piece: null,
  sequence: 1,
  creator_id: 1,
  lot_id: 1,
  position_id: 1,
  source_process_id: null,
  fabrication_method_required_external: false,
  fabrication_method_default_supplier_id: null,
  position_needs_machine: true,
  position_quantity: 10,
  position_quantity_remaining: 10,
  role: 'fabrication' as const,
  fabrication_method_id: 5,
  fabrication_method_name: 'Milling',
  fabrication_method_requires_machine: true,
  inspection_method_id: null,
  inspection_method_name: null,
  inspection_method_requires_evidence: null,
}

function makeStep(
  positionKind: LotSummaryStepResponse['position_kind'],
  positionStatus: LotSummaryStepResponse['position_status'],
  overrides: Partial<LotSummaryStepResponse> = {},
): LotSummaryStepResponse {
  return {
    ...STEP_BASE,
    position_kind: positionKind,
    position_status: positionStatus,
    ...overrides,
  } as LotSummaryStepResponse
}

function makeOrder(
  overrides: Partial<LotSummaryProductionOrderResponse> = {},
): LotSummaryProductionOrderResponse {
  return {
    id: 1,
    status: 'queued',
    machine_id: null,
    machine_internal_name: '',
    machine_pool_id: null,
    machine_pool_name: '',
    planned_start: null,
    planned_end: null,
    actual_start: null,
    actual_end: null,
    quantity_completed: 0,
    edit_version: 0,
    planned_by_name: null,
    conflicts: [],
    earliest_start_date: null,
    earliest_start_reason: null,
    ...overrides,
  }
}

function makePosition(
  overrides: Partial<LotSummaryPositionResponse> = {},
): LotSummaryPositionResponse {
  return {
    id: 1,
    kind: 'internal',
    order_id: null,
    order_number: '',
    order_item_id: null,
    order_item_status: '',
    order_item_closed_short: false,
    order_item_quantity: null,
    order_item_quantity_delivered: null,
    order_item_unit: '',
    order_item_items_per_unit: 1,
    order_item_edit_version: 0,
    expected_delivery_date: null,
    delivery_date: null,
    expected_pickup_date: null,
    ready_for_pickup_date: null,
    delivery_record_count: 0,
    ordered_by_name: null,
    production_orders: [],
    lead_days: null,
    lead_days_source: null,
    planned_delivery_date: null,
    planned_pickup_date: null,
    ...overrides,
  }
}

describe('plannedDateTooltip', () => {
  it('returns undefined when the date is neither overdue nor conflicted', () => {
    expect(plannedDateTooltip(makePlannedInfo(), t)).toBeUndefined()
  })

  it('explains an overdue date with no conflicts', () => {
    const info = makePlannedInfo({ isOverdue: true })
    expect(plannedDateTooltip(info, t)).toBe(t('production.lots.tooltips.overdue'))
  })

  it('lists the conflicts when there is no overdue flag', () => {
    const info = makePlannedInfo({ conflicts: ['waiting_on_predecessor'] })
    expect(plannedDateTooltip(info, t)).toBe(t('productionQueue.conflicts.waiting_on_predecessor'))
  })

  it('lists the machine_down conflict like any other conflict reason', () => {
    const info = makePlannedInfo({ conflicts: ['machine_down'] })
    expect(plannedDateTooltip(info, t)).toBe(t('productionQueue.conflicts.machine_down'))
  })

  it('combines the overdue sentence and the conflicts list, one per line', () => {
    const info = makePlannedInfo({ isOverdue: true, conflicts: ['waiting_on_predecessor'] })
    const result = plannedDateTooltip(info, t)
    expect(result).toBe(
      [
        t('production.lots.tooltips.overdue'),
        t('productionQueue.conflicts.waiting_on_predecessor'),
      ].join('\n'),
    )
  })

  it.each([
    ['predecessor', 'production.lots.tooltips.earliestStart.predecessor'],
    ['material', 'production.lots.tooltips.earliestStart.material'],
    ['not_before', 'production.lots.tooltips.earliestStart.notBefore'],
    ['queue', 'production.lots.tooltips.earliestStart.queue'],
  ])('names the %s reason with its date', (reason, key) => {
    const info = makePlannedInfo({ earliestStart: { reason, date: new Date(2026, 8, 24) } })
    expect(plannedDateTooltip(info, t)).toBe(t(key, { date: '2026-09-24' }))
  })

  it.each([
    ['unknown_chain', 'production.lots.tooltips.earliestStart.unknownChain'],
    ['missing_material', 'production.lots.tooltips.earliestStart.missingMaterial'],
  ])('names the %s reason without a date', (reason, key) => {
    const info = makePlannedInfo({ earliestStart: { reason, date: null } })
    expect(plannedDateTooltip(info, t)).toBe(t(key))
  })

  it('shows nothing for a reason with no date it needs (predecessor/material/not_before/queue) when the date is missing', () => {
    const info = makePlannedInfo({ earliestStart: { reason: 'predecessor', date: null } })
    expect(plannedDateTooltip(info, t)).toBeUndefined()
  })

  it('shows nothing for a reason without a dedicated sentence (in_progress, pinned, none)', () => {
    for (const reason of ['in_progress', 'pinned', 'none']) {
      const info = makePlannedInfo({ earliestStart: { reason, date: new Date(2026, 8, 24) } })
      expect(plannedDateTooltip(info, t)).toBeUndefined()
    }
  })

  it('puts the earliest-start sentence first, ahead of overdue and conflicts', () => {
    const info = makePlannedInfo({
      earliestStart: { reason: 'predecessor', date: new Date(2026, 8, 24) },
      isOverdue: true,
      conflicts: ['waiting_on_predecessor'],
    })
    expect(plannedDateTooltip(info, t)).toBe(
      [
        t('production.lots.tooltips.earliestStart.predecessor', { date: '2026-09-24' }),
        t('production.lots.tooltips.overdue'),
        t('productionQueue.conflicts.waiting_on_predecessor'),
      ].join('\n'),
    )
  })
})

describe('plannedAttributionTooltip', () => {
  it('returns undefined when there is nothing to attribute', () => {
    expect(plannedAttributionTooltip(makePlannedInfo(), t)).toBeUndefined()
  })

  it('external_typed names the order and the line owner, never claiming they "set" the date', () => {
    const info = makePlannedInfo({
      attribution: makeAttribution({ kind: 'external_typed', orderNumber: 'B-42', personName: 'Alice' }),
    })
    expect(plannedAttributionTooltip(info, t)).toBe(
      t('production.lots.tooltips.attribution.externalTyped', { order: 'B-42', person: 'Alice' }),
    )
  })

  it('external_typed without a known person falls back to the order-only sentence', () => {
    const info = makePlannedInfo({
      attribution: makeAttribution({ kind: 'external_typed', orderNumber: 'B-42', personName: null }),
    })
    expect(plannedAttributionTooltip(info, t)).toBe(
      t('production.lots.tooltips.attribution.externalTypedNoPerson', { order: 'B-42' }),
    )
  })

  it('external_typed with no order number at all shows nothing', () => {
    const info = makePlannedInfo({
      attribution: makeAttribution({ kind: 'external_typed', orderNumber: null, personName: 'Alice' }),
    })
    expect(plannedAttributionTooltip(info, t)).toBeUndefined()
  })

  it('external_forecast names the forecast pickup and delivery dates', () => {
    const info = makePlannedInfo({
      attribution: makeAttribution({
        kind: 'external_forecast',
        plannedPickupDate: new Date(2026, 8, 24),
        plannedDeliveryDate: new Date(2026, 8, 28),
      }),
    })
    expect(plannedAttributionTooltip(info, t)).toBe(
      t('production.lots.tooltips.attribution.externalForecast', {
        pickup: '2026-09-24',
        delivery: '2026-09-28',
        leadDaysNote: '',
      }),
    )
  })

  it('external_forecast without a resolved lead time shows no lead-days note', () => {
    const info = makePlannedInfo({
      attribution: makeAttribution({
        kind: 'external_forecast',
        plannedPickupDate: new Date(2026, 8, 24),
        plannedDeliveryDate: new Date(2026, 8, 28),
        leadDays: null,
        leadDaysSource: null,
      }),
    })
    expect(plannedAttributionTooltip(info, t)).not.toContain('lead day')
  })

  it.each([
    ['supplier', t('production.lots.tooltips.attribution.leadDaysSourceSupplier')],
    ['method', t('production.lots.tooltips.attribution.leadDaysSourceMethod')],
    ['default', t('production.lots.tooltips.attribution.leadDaysSourceDefault')],
  ])('external_forecast names the lead-days count and %s source', (source, sourceLabel) => {
    const info = makePlannedInfo({
      attribution: makeAttribution({
        kind: 'external_forecast',
        plannedPickupDate: new Date(2026, 8, 24),
        plannedDeliveryDate: new Date(2026, 8, 28),
        leadDays: 3,
        leadDaysSource: source,
      }),
    })
    expect(plannedAttributionTooltip(info, t)).toBe(
      t('production.lots.tooltips.attribution.externalForecast', {
        pickup: '2026-09-24',
        delivery: '2026-09-28',
        leadDaysNote: t('production.lots.tooltips.attribution.leadDaysNote', {
          days: 3,
          source: sourceLabel,
        }),
      }),
    )
  })

  it('manual_pinned names the person who pinned the schedule', () => {
    const info = makePlannedInfo({ attribution: makeAttribution({ kind: 'manual_pinned', personName: 'Bob' }) })
    expect(plannedAttributionTooltip(info, t)).toBe(
      t('production.lots.tooltips.attribution.manualPinned', { person: 'Bob' }),
    )
  })

  it('manual_pinned with no person shows nothing', () => {
    const info = makePlannedInfo({ attribution: makeAttribution({ kind: 'manual_pinned', personName: null }) })
    expect(plannedAttributionTooltip(info, t)).toBeUndefined()
  })

  it('auto_planner names the resolved machine', () => {
    const info = makePlannedInfo({
      attribution: makeAttribution({ kind: 'auto_planner', machineName: 'Mill A' }),
    })
    expect(plannedAttributionTooltip(info, t)).toBe(
      t('production.lots.tooltips.attribution.autoPlanner', { target: 'Mill A' }),
    )
  })

  it('auto_planner falls back to the pool when not yet resolved to a machine', () => {
    const info = makePlannedInfo({
      attribution: makeAttribution({ kind: 'auto_planner', poolName: 'Mill Pool' }),
    })
    expect(plannedAttributionTooltip(info, t)).toBe(
      t('production.lots.tooltips.attribution.autoPlanner', {
        target: t('production.lots.tooltips.attribution.targetPool', { pool: 'Mill Pool' }),
      }),
    )
  })

  it('auto_planner names "no machine" for a manual step', () => {
    const info = makePlannedInfo({ attribution: makeAttribution({ kind: 'auto_planner' }) })
    expect(plannedAttributionTooltip(info, t)).toBe(
      t('production.lots.tooltips.attribution.autoPlanner', {
        target: t('production.lots.tooltips.attribution.targetNoMachine'),
      }),
    )
  })

  it('actual states the date is confirmed, without naming anyone', () => {
    const info = makePlannedInfo({ attribution: makeAttribution({ kind: 'actual' }) })
    expect(plannedAttributionTooltip(info, t)).toBe(t('production.lots.tooltips.attribution.actual'))
  })
})

describe('positionStatusTooltip', () => {
  it('pending (internal): no supplier order or production order yet', () => {
    const step = makeStep('internal', 'pending')
    expect(positionStatusTooltip(step, undefined, t)).toBe(t('production.lots.tooltips.positionStatus.pending'))
  })

  it('allocated (pending, external): names the order and its line status', () => {
    const step = makeStep('external', 'pending')
    const position = makePosition({ order_number: 'B-42', order_item_status: 'requested' })
    expect(positionStatusTooltip(step, position, t)).toBe(
      t('production.lots.tooltips.positionStatus.allocated', { order: 'B-42', status: 'requested' }),
    )
  })

  it('allocated falls back to the plain status word when the order number is missing', () => {
    const step = makeStep('external', 'pending')
    expect(positionStatusTooltip(step, undefined, t)).toBe(t('production.lots.positionStatus.allocated'))
  })

  it('ordered (ordered_or_queued, external): names the order and the expected delivery date', () => {
    const step = makeStep('external', 'ordered_or_queued')
    const position = makePosition({ order_number: 'B-42', expected_delivery_date: '2026-09-04' })
    expect(positionStatusTooltip(step, position, t)).toBe(
      t('production.lots.tooltips.positionStatus.ordered', { order: 'B-42', date: '2026-09-04' }),
    )
  })

  it('ordered falls back to the plain status word when the expected date is missing', () => {
    const step = makeStep('external', 'ordered_or_queued')
    const position = makePosition({ order_number: 'B-42' })
    expect(positionStatusTooltip(step, position, t)).toBe(t('production.lots.positionStatus.ordered'))
  })

  it('queued (ordered_or_queued, internal): names the assigned machine', () => {
    const step = makeStep('internal', 'ordered_or_queued')
    const position = makePosition({ production_orders: [makeOrder({ machine_internal_name: 'Mill A' })] })
    expect(positionStatusTooltip(step, position, t)).toBe(
      t('production.lots.tooltips.positionStatus.queuedOnMachine', { machine: 'Mill A' }),
    )
  })

  it('queued falls back to the pool while not yet resolved to a machine', () => {
    const step = makeStep('internal', 'ordered_or_queued')
    const position = makePosition({ production_orders: [makeOrder({ machine_pool_name: 'Mill Pool' })] })
    expect(positionStatusTooltip(step, position, t)).toBe(
      t('production.lots.tooltips.positionStatus.queuedInPool', { pool: 'Mill Pool' }),
    )
  })

  it('queued names "no machine" for a manual step', () => {
    const step = makeStep('internal', 'ordered_or_queued')
    const position = makePosition({ production_orders: [makeOrder()] })
    expect(positionStatusTooltip(step, position, t)).toBe(
      t('production.lots.tooltips.positionStatus.queuedNoMachine'),
    )
  })

  it('queued falls back to the plain status word when there is no active order', () => {
    const step = makeStep('internal', 'ordered_or_queued')
    expect(positionStatusTooltip(step, undefined, t)).toBe(t('production.lots.positionStatus.queued'))
  })

  it('an ambiguous mixed ordered_or_queued status falls back to the plain status word', () => {
    const step = makeStep('mixed', 'ordered_or_queued')
    expect(positionStatusTooltip(step, undefined, t)).toBe(t('production.lots.positionStatus.ordered_or_queued'))
  })

  it('in_progress: names the actual start date', () => {
    const step = makeStep('internal', 'in_progress')
    const actualStart = '2026-09-10T12:00:00Z'
    const position = makePosition({
      production_orders: [makeOrder({ status: 'in_progress', actual_start: actualStart })],
    })
    expect(positionStatusTooltip(step, position, t)).toBe(
      t('production.lots.tooltips.positionStatus.inProgress', {
        date: dateToParam(toLocalDayStart(actualStart)),
      }),
    )
  })

  it('in_progress falls back to the plain status word when no order has actually started', () => {
    const step = makeStep('internal', 'in_progress')
    expect(positionStatusTooltip(step, undefined, t)).toBe(t('production.lots.positionStatus.in_progress'))
  })

  it('partially_completed: names the delivered/total split', () => {
    const step = makeStep('external', 'partially_completed')
    const position = makePosition({ order_item_quantity_delivered: 3, order_item_quantity: 10 })
    expect(positionStatusTooltip(step, position, t)).toBe(
      t('production.lots.tooltips.positionStatus.partiallyCompleted', { done: 3, qty: 10 }),
    )
  })

  it('partially_completed falls back to the plain status word without delivery counts', () => {
    const step = makeStep('internal', 'partially_completed')
    expect(positionStatusTooltip(step, undefined, t)).toBe(t('production.lots.positionStatus.partially_completed'))
  })

  it('partially_completed (internal): sums each active order own quantity_completed against the position total', () => {
    const step = makeStep('internal', 'partially_completed', { position_quantity: 10 })
    const position = makePosition({
      production_orders: [
        makeOrder({ id: 1, quantity_completed: 4 }),
        makeOrder({ id: 2, quantity_completed: 2, status: 'canceled' }),
      ],
    })
    expect(positionStatusTooltip(step, position, t)).toBe(
      t('production.lots.tooltips.positionStatus.partiallyCompleted', { done: 4, qty: 10 }),
    )
  })

  it('partially_completed (internal): falls back to the plain status word when nothing is completed yet', () => {
    const step = makeStep('internal', 'partially_completed', { position_quantity: 10 })
    const position = makePosition({ production_orders: [makeOrder({ quantity_completed: 0 })] })
    expect(positionStatusTooltip(step, position, t)).toBe(t('production.lots.positionStatus.partially_completed'))
  })

  it('completed and canceled are plain, data-independent sentences', () => {
    expect(positionStatusTooltip(makeStep('internal', 'completed'), undefined, t)).toBe(
      t('production.lots.tooltips.positionStatus.completed'),
    )
    expect(positionStatusTooltip(makeStep('internal', 'canceled'), undefined, t)).toBe(
      t('production.lots.tooltips.positionStatus.canceled'),
    )
  })
})

describe('methodTooltipSuffix', () => {
  it('returns undefined without a position', () => {
    expect(methodTooltipSuffix(undefined, t)).toBeUndefined()
  })

  it('names the supplier order for an external position', () => {
    const position = makePosition({ kind: 'external', order_number: 'B-42' })
    expect(methodTooltipSuffix(position, t)).toBe(
      t('production.lots.tooltips.method.supplierLine', { order: 'B-42' }),
    )
  })

  it('returns undefined for an external position with no order number', () => {
    const position = makePosition({ kind: 'external' })
    expect(methodTooltipSuffix(position, t)).toBeUndefined()
  })

  it('names the machine for an internal position', () => {
    const position = makePosition({
      kind: 'internal',
      production_orders: [makeOrder({ machine_internal_name: 'Mill A' })],
    })
    expect(methodTooltipSuffix(position, t)).toBe(
      t('production.lots.tooltips.method.machineLine', { target: 'Mill A' }),
    )
  })

  it('returns undefined for an internal position with no active production order', () => {
    const position = makePosition({ kind: 'internal', production_orders: [] })
    expect(methodTooltipSuffix(position, t)).toBeUndefined()
  })

  it('names both the supplier and the machine for a mixed position', () => {
    const position = makePosition({
      kind: 'mixed',
      order_number: 'B-42',
      production_orders: [makeOrder({ machine_internal_name: 'Mill A' })],
    })
    expect(methodTooltipSuffix(position, t)).toBe(
      [
        t('production.lots.tooltips.method.supplierLine', { order: 'B-42' }),
        t('production.lots.tooltips.method.machineLine', { target: 'Mill A' }),
      ].join('\n'),
    )
  })
})
