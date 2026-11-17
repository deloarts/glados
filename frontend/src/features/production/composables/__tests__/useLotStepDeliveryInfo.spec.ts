import { describe, it, expect } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'

import { i18n } from '@/core/i18n'
import { useLotStepDeliveryInfo } from '../useLotStepDeliveryInfo'

import type {
  LotSummaryPositionResponse,
  LotSummaryProductionOrderResponse,
} from '../../types/productionLotsResponse'

// useLotStepDeliveryInfo calls useI18n() internally, which needs an active
// component instance. Mount a throwaway component whose setup() invokes it
// and captures the result, same pattern as createCatalogueColumnsStore.spec.ts.
function mountComposable() {
  let result!: ReturnType<typeof useLotStepDeliveryInfo>
  mount(
    defineComponent({
      setup() {
        result = useLotStepDeliveryInfo(ref([]))
        return () => h('div')
      },
    }),
    { global: { plugins: [i18n] } },
  )
  return result
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

describe('useLotStepDeliveryInfo sourceOrderInfoFor', () => {
  it('shows the machine name when one is assigned', () => {
    const { sourceOrderInfoFor } = mountComposable()
    const position = makePosition({
      production_orders: [makeOrder({ machine_id: 5, machine_internal_name: 'Mill A' })],
    })

    expect(sourceOrderInfoFor(position)?.machineNames).toEqual(['Mill A'])
  })

  // In the lots table, a pool-assigned-but-unresolved order (machine_id
  // null, machine_pool_id set) shows the pool's name instead of falling all
  // the way through to "Not assigned".
  it('falls back to the pool name when the order is pool-assigned but not yet resolved to a machine', () => {
    const { sourceOrderInfoFor } = mountComposable()
    const position = makePosition({
      production_orders: [makeOrder({ machine_pool_id: 9, machine_pool_name: 'Mill Pool' })],
    })

    expect(sourceOrderInfoFor(position)?.machineNames).toEqual(['Mill Pool'])
  })

  it('falls back to "Not assigned" when neither a machine nor a pool is set', () => {
    const { sourceOrderInfoFor } = mountComposable()
    const position = makePosition({ production_orders: [makeOrder()] })

    expect(sourceOrderInfoFor(position)?.machineNames).toEqual(['Not assigned'])
  })

  it('prefers the machine name over the pool once resolved (both set)', () => {
    const { sourceOrderInfoFor } = mountComposable()
    const position = makePosition({
      production_orders: [
        makeOrder({ machine_id: 5, machine_internal_name: 'Mill A', machine_pool_id: 9, machine_pool_name: 'Mill Pool' }),
      ],
    })

    expect(sourceOrderInfoFor(position)?.machineNames).toEqual(['Mill A'])
  })
})

// plannedDateFor's `attribution` field: who/what produced the shown date,
// consumed by the lots table's tooltip (see utils/lotStepDisplay.ts's
// plannedAttributionTooltip). Each case below asserts the whole
// PlannedInfo.attribution object, not just `kind`, so a regression that
// drops a field (e.g. forgets to null out machineName on an external
// entry) doesn't slip through a partial match.
describe('useLotStepDeliveryInfo plannedDateFor attribution', () => {
  it('returns a null-kind attribution when nothing is known at all', () => {
    const { plannedDateFor } = mountComposable()
    const position = makePosition({ kind: 'unassigned' })

    expect(plannedDateFor(position).attribution.kind).toBeNull()
  })

  it('external_typed: a typed expected delivery date attributes the order and the line owner', () => {
    const { plannedDateFor } = mountComposable()
    const position = makePosition({
      kind: 'external',
      order_id: 3,
      order_number: 'B-42',
      order_item_id: 9,
      expected_delivery_date: '2026-09-04',
      ordered_by_name: 'Alice',
    })

    expect(plannedDateFor(position).attribution).toEqual({
      kind: 'external_typed',
      personName: 'Alice',
      orderId: 3,
      orderNumber: 'B-42',
      machineName: null,
      poolName: null,
      plannedPickupDate: null,
      plannedDeliveryDate: null,
      leadDays: null,
      leadDaysSource: null,
    })
  })

  it('external_forecast: no typed date but a computed forecast attributes the auto-planner with both forecast dates, and the date shown is the forecast', () => {
    const { plannedDateFor } = mountComposable()
    const position = makePosition({
      kind: 'external',
      order_id: 3,
      order_number: 'B-42',
      order_item_id: 9,
      expected_delivery_date: null,
      planned_pickup_date: '2026-09-24',
      planned_delivery_date: '2026-09-28',
    })

    const result = plannedDateFor(position)
    expect(result.date).toEqual(new Date(2026, 8, 28))
    expect(result.attribution).toEqual({
      kind: 'external_forecast',
      personName: null,
      orderId: 3,
      orderNumber: 'B-42',
      machineName: null,
      poolName: null,
      plannedPickupDate: new Date(2026, 8, 24),
      plannedDeliveryDate: new Date(2026, 8, 28),
      leadDays: null,
      leadDaysSource: null,
    })
  })

  it('actual: a delivered external item is attributed as a confirmed fact, not a typed promise', () => {
    const { plannedDateFor } = mountComposable()
    const position = makePosition({
      kind: 'external',
      order_id: 3,
      order_number: 'B-42',
      order_item_id: 9,
      order_item_status: 'delivered',
      order_item_closed_short: false,
      delivery_date: '2026-09-10',
      expected_delivery_date: '2026-09-04',
      ordered_by_name: 'Alice',
    })

    expect(plannedDateFor(position).attribution.kind).toBe('actual')
  })

  it('manual_pinned: an internal order with a planned_by_name attributes that person plus its machine', () => {
    const { plannedDateFor } = mountComposable()
    const position = makePosition({
      kind: 'internal',
      production_orders: [
        makeOrder({
          id: 7,
          status: 'queued',
          planned_end: '2026-09-10T00:00:00Z',
          planned_by_name: 'Bob',
          machine_internal_name: 'Mill A',
        }),
      ],
    })

    expect(plannedDateFor(position).attribution).toEqual({
      kind: 'manual_pinned',
      personName: 'Bob',
      orderId: 7,
      orderNumber: null,
      machineName: 'Mill A',
      poolName: null,
      plannedPickupDate: null,
      plannedDeliveryDate: null,
      leadDays: null,
      leadDaysSource: null,
    })
  })

  it('auto_planner: an internal order with no planned_by_name attributes the scheduler plus its pool', () => {
    const { plannedDateFor } = mountComposable()
    const position = makePosition({
      kind: 'internal',
      production_orders: [
        makeOrder({
          id: 7,
          status: 'queued',
          planned_end: '2026-09-10T00:00:00Z',
          planned_by_name: null,
          machine_pool_id: 4,
          machine_pool_name: 'Mill Pool',
        }),
      ],
    })

    expect(plannedDateFor(position).attribution).toEqual({
      kind: 'auto_planner',
      personName: null,
      orderId: 7,
      orderNumber: null,
      machineName: null,
      poolName: 'Mill Pool',
      plannedPickupDate: null,
      plannedDeliveryDate: null,
      leadDays: null,
      leadDaysSource: null,
    })
  })

  it('actual: a completed internal order is attributed as a confirmed fact regardless of who scheduled it', () => {
    const { plannedDateFor } = mountComposable()
    const position = makePosition({
      kind: 'internal',
      production_orders: [
        makeOrder({ id: 7, status: 'completed', actual_end: '2026-09-10T00:00:00Z', planned_by_name: 'Bob' }),
      ],
    })

    expect(plannedDateFor(position).attribution.kind).toBe('actual')
  })

  it('a mixed position attributes whichever candidate (external or internal) won as the shown date', () => {
    const { plannedDateFor } = mountComposable()
    const position = makePosition({
      kind: 'mixed',
      order_id: 3,
      order_number: 'B-42',
      order_item_id: 9,
      expected_delivery_date: '2026-09-01',
      ordered_by_name: 'Alice',
      production_orders: [
        makeOrder({
          id: 7,
          status: 'queued',
          planned_end: '2026-09-10T00:00:00Z',
          machine_internal_name: 'Mill A',
        }),
      ],
    })

    const result = plannedDateFor(position)
    // The internal order (09-10) finishes later than the external typed
    // date (09-01), so it wins as `date`, and the attribution follows it.
    expect(result.date).toEqual(new Date('2026-09-10T00:00:00Z'))
    expect(result.attribution.kind).toBe('auto_planner')
    expect(result.attribution.machineName).toBe('Mill A')
  })

  it('external_forecast: carries the resolved lead days and source of the position', () => {
    const { plannedDateFor } = mountComposable()
    const position = makePosition({
      kind: 'external',
      order_id: 3,
      order_number: 'B-42',
      order_item_id: 9,
      expected_delivery_date: null,
      planned_pickup_date: '2026-09-24',
      planned_delivery_date: '2026-09-28',
      lead_days: 4,
      lead_days_source: 'method',
    })

    const result = plannedDateFor(position)
    expect(result.attribution.leadDays).toBe(4)
    expect(result.attribution.leadDaysSource).toBe('method')
  })
})

// plannedDateFor's `earliestStart` field: what currently governs an
// internal order's earliest possible start (see the backend's
// explain_earliest_start), consumed by utils/lotStepDisplay.ts's
// plannedDateTooltip.
describe('useLotStepDeliveryInfo plannedDateFor earliestStart', () => {
  it('is null-reason for an external position (the backend never resolves one there)', () => {
    const { plannedDateFor } = mountComposable()
    const position = makePosition({
      kind: 'external',
      expected_delivery_date: '2026-09-04',
    })

    expect(plannedDateFor(position).earliestStart).toEqual({ reason: null, date: null })
  })

  it('carries an open internal order reason and date through', () => {
    const { plannedDateFor } = mountComposable()
    const position = makePosition({
      kind: 'internal',
      production_orders: [
        makeOrder({
          id: 7,
          status: 'queued',
          planned_end: '2026-09-10T00:00:00Z',
          earliest_start_reason: 'predecessor',
          earliest_start_date: '2026-09-08',
        }),
      ],
    })

    expect(plannedDateFor(position).earliestStart).toEqual({
      reason: 'predecessor',
      date: new Date(2026, 8, 8),
    })
  })

  it('is null-reason for a completed internal order - nothing left to explain', () => {
    const { plannedDateFor } = mountComposable()
    const position = makePosition({
      kind: 'internal',
      production_orders: [
        makeOrder({
          id: 7,
          status: 'completed',
          actual_end: '2026-09-10T00:00:00Z',
          earliest_start_reason: 'predecessor',
          earliest_start_date: '2026-09-08',
        }),
      ],
    })

    expect(plannedDateFor(position).earliestStart).toEqual({ reason: null, date: null })
  })
})
