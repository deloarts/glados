import { describe, it, expect } from 'vitest'

import { buildLotStateSummary } from '../lotStateSummary'
import {
  makeLotResponse,
  makeProductionOrderResponse,
  makeSourceItemDemandResponse,
} from '@/test-utils/factories'

import type { LotStateSummaryInput } from '../lotStateSummary'
import type {
  LotPositionResponse,
  LotResponse,
  LotStepResponse,
} from '../../../types/productionLotsResponse'
import type { ProductionOrderResponse } from '../../../types/productionOrdersResponse'
import type { SourceItemDemandResponse } from '@/features/source-items'

function makePosition(overrides: Partial<LotPositionResponse> = {}): LotPositionResponse {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    created: '2026-07-01',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    sequence: 1,
    kind: 'internal',
    status: 'in_progress',
    quantity: 10,
    quantity_completed: 4,
    quantity_remaining: 6,
    note: null,
    creator_id: 1,
    lot_id: 1,
    steps: [],
    order_item_id: null,
    order_id: null,
    order_number: '',
    supplier_name: '',
    order_item_status: '',
    order_item_closed_short: false,
    earlier_order_lines: [],
    expected_delivery_date: null,
    production_orders: [],
    actions: [],
    planned_delivery_date: null,
    planned_pickup_date: null,
    ...overrides,
  }
}

const STEP_BASE = {
  id: 1,
  public_id: '00000000-0000-0000-0000-0000000000aa',
  created: '2026-07-01',
  note: null,
  estimated_setup_minutes: null,
  estimated_minutes_per_piece: null,
  time_budget_per_piece: null,
  sequence: 1,
  creator_id: 1,
  fabrication_method_name: '',
  fabrication_method_required_external: false,
  fabrication_method_default_supplier_id: null,
  lot_id: 1,
  position_id: 1,
  source_process_id: null,
}

function makeFabricationStep(overrides: Partial<LotStepResponse> = {}): LotStepResponse {
  return {
    ...STEP_BASE,
    role: 'fabrication',
    fabrication_method_id: 5,
    fabrication_method_name: 'Milling',
    fabrication_method_requires_machine: true,
    inspection_method_id: null,
    inspection_method_name: null,
    inspection_method_requires_evidence: null,
    ...overrides,
  } as LotStepResponse
}

function makeInspectionStep(overrides: Partial<LotStepResponse> = {}): LotStepResponse {
  return {
    ...STEP_BASE,
    role: 'inspection',
    fabrication_method_id: null,
    fabrication_method_requires_machine: false,
    inspection_method_id: 1,
    inspection_method_name: 'Visual Inspection',
    inspection_method_requires_evidence: false,
    ...overrides,
  } as LotStepResponse
}

function makeLot(overrides: Partial<LotResponse> = {}): LotResponse {
  return makeLotResponse({
    source_item_id: 5,
    source_label: 'Stock item',
    positions: [makePosition()],
    ...overrides,
  })
}

function makeOrder(overrides: Partial<ProductionOrderResponse> = {}): ProductionOrderResponse {
  return makeProductionOrderResponse({
    production_order_number: 'PO-0001',
    quantity: 5,
    machine_internal_name: 'Mill 1',
    lot_number: 'LOT-0001',
    ...overrides,
  })
}

function makeDemand(overrides: Partial<SourceItemDemandResponse> = {}): SourceItemDemandResponse {
  return makeSourceItemDemandResponse({
    id: 9,
    public_id: '99999999-9999-9999-9999-999999999999',
    status: 'ordered',
    created: '2026-07-01',
    quantity: 10,
    unit: 'kg',
    source_item_id: 5,
    source_item: null,
    project_id: 42,
    project_description: '',
    ...overrides,
  })
}

function summarize(overrides: Partial<LotStateSummaryInput> = {}) {
  return buildLotStateSummary({
    lot: makeLot(),
    productionOrders: [],
    sourceItemDemand: null,
    sourceItemDemandArrived: 0,
    today: '2026-08-05',
    ...overrides,
  })
}

describe('buildLotStateSummary', () => {
  it('short-circuits to a single terminal signal for completed lots, ignoring other blockers', () => {
    const signals = summarize({
      lot: makeLot({
        status: 'completed',
        required_delivery_date: '2026-01-01',
        positions: [makePosition({ kind: 'unassigned' })],
      }),
    })
    expect(signals).toEqual([
      {
        id: 'completed',
        labelKey: 'production.lots.detail.state.completed',
        severity: 'success',
        icon: expect.any(String),
      },
    ])
  })

  it('short-circuits to a single terminal signal for canceled lots', () => {
    const signals = summarize({ lot: makeLot({ status: 'canceled' }) })
    expect(signals.map((s) => s.id)).toEqual(['canceled'])
  })

  it('short-circuits to "on hold" and ignores an overdue delivery date', () => {
    const signals = summarize({
      lot: makeLot({ status: 'on_hold', required_delivery_date: '2026-01-01' }),
    })
    expect(signals.map((s) => s.id)).toEqual(['onHold'])
  })

  it('reports deliveryLate when the required delivery date is in the past', () => {
    const signals = summarize({
      lot: makeLot({ required_delivery_date: '2026-08-01' }),
      today: '2026-08-05',
    })
    expect(signals.map((s) => s.id)).toContain('deliveryLate')
  })

  it('does not report deliveryLate when the required delivery date is today or in the future', () => {
    const today = summarize({
      lot: makeLot({ required_delivery_date: '2026-08-05' }),
      today: '2026-08-05',
    })
    const future = summarize({
      lot: makeLot({ required_delivery_date: '2026-08-06' }),
      today: '2026-08-05',
    })
    expect(today.map((s) => s.id)).not.toContain('deliveryLate')
    expect(future.map((s) => s.id)).not.toContain('deliveryLate')
  })

  it("trusts a production order's own waiting_on_raw_material flag when orders exist", () => {
    const signals = summarize({
      lot: makeLot({ input_demand_id: 7 }),
      productionOrders: [makeOrder({ waiting_on_raw_material: true })],
      sourceItemDemand: makeDemand({ quantity: 10 }),
      sourceItemDemandArrived: 10, // fully arrived; the order flag still wins
    })
    expect(signals.map((s) => s.id)).toContain('waitingOnMaterial')
  })

  it('falls back to the demand-arrived comparison only when no production orders exist yet', () => {
    const waiting = summarize({
      lot: makeLot({ input_demand_id: 7 }),
      productionOrders: [],
      sourceItemDemand: makeDemand({ quantity: 10 }),
      sourceItemDemandArrived: 4,
    })
    expect(waiting.map((s) => s.id)).toContain('waitingOnMaterial')

    // Same under-delivered demand, but a (non-flagged) order already exists:
    // the fallback must not fire once there is something to trust instead.
    const scheduled = summarize({
      lot: makeLot({ input_demand_id: 7 }),
      productionOrders: [makeOrder({ waiting_on_raw_material: false })],
      sourceItemDemand: makeDemand({ quantity: 10 }),
      sourceItemDemandArrived: 4,
    })
    expect(scheduled.map((s) => s.id)).not.toContain('waitingOnMaterial')
  })

  it('reports no material source when nothing is configured', () => {
    const signals = summarize({
      lot: makeLot({
        source_bought_item_id: null,
        source_item_id: null,
        source_made_item_id: null,
        input_demand_id: null,
        is_alteration: false,
      }),
    })
    expect(signals.map((s) => s.id)).toContain('noMaterialSource')
  })

  it('does not report no-material-source for an alteration lot', () => {
    const signals = summarize({
      lot: makeLot({
        source_bought_item_id: null,
        source_item_id: null,
        source_made_item_id: null,
        input_demand_id: null,
        is_alteration: true,
      }),
    })
    expect(signals.map((s) => s.id)).not.toContain('noMaterialSource')
  })

  it('counts unassigned positions as "not planned"', () => {
    const signals = summarize({
      lot: makeLot({
        positions: [
          makePosition({ id: 1, kind: 'unassigned' }),
          makePosition({ id: 2, kind: 'unassigned' }),
          makePosition({ id: 3, kind: 'internal' }),
        ],
      }),
    })
    const notPlanned = signals.find((s) => s.id === 'notPlanned')
    expect(notPlanned?.labelParams).toEqual({ count: 2 })
  })

  it('reports waiting on supplier for an external position still on order', () => {
    const signals = summarize({
      lot: makeLot({
        positions: [makePosition({ kind: 'external', status: 'ordered_or_queued' })],
      }),
    })
    expect(signals.map((s) => s.id)).toContain('waitingOnSupplier')
  })

  it('dedupes conflicts across orders and drops informational-only ones', () => {
    const signals = summarize({
      productionOrders: [
        makeOrder({ id: 1, conflicts: ['no_machine_assigned', 'estimate_from_time_budget'] }),
        makeOrder({ id: 2, conflicts: ['no_machine_assigned', 'waiting_on_predecessor'] }),
      ],
    })
    const conflictIds = signals.filter((s) => s.id.startsWith('conflict-')).map((s) => s.id)
    expect(conflictIds).toEqual(['conflict-no_machine_assigned'])
  })

  it('does not duplicate a past_target_date conflict once deliveryLate has already fired', () => {
    const signals = summarize({
      lot: makeLot({ required_delivery_date: '2026-08-01' }),
      productionOrders: [makeOrder({ conflicts: ['past_target_date'] })],
      today: '2026-08-05',
    })
    expect(signals.filter((s) => s.id === 'deliveryLate')).toHaveLength(1)
    expect(signals.map((s) => s.id)).not.toContain('conflict-past_target_date')
  })

  it('does not duplicate a past_target_date conflict once deliveryWillBeLate has already fired', () => {
    const signals = summarize({
      lot: makeLot({ required_delivery_date: '2026-08-06' }),
      productionOrders: [
        makeOrder({
          lot_position_id: 1,
          status: 'queued',
          planned_end: '2026-08-10T12:00:00',
          conflicts: ['past_target_date'],
        }),
      ],
      today: '2026-08-05',
    })
    expect(signals.filter((s) => s.id === 'deliveryWillBeLate')).toHaveLength(1)
    expect(signals.map((s) => s.id)).not.toContain('conflict-past_target_date')
  })

  it('reports "in progress" when nothing else is blocking but an order is running', () => {
    const signals = summarize({
      lot: makeLot({ source_item_id: null, input_demand_id: null, is_alteration: true }),
      productionOrders: [makeOrder({ status: 'in_progress' })],
    })
    expect(signals.map((s) => s.id)).toEqual(['inProgress'])
  })

  it('falls back to "on track" for a lot with nothing notable at all', () => {
    const signals = summarize({
      lot: makeLot({ source_item_id: null, input_demand_id: null, is_alteration: true }),
    })
    expect(signals.map((s) => s.id)).toEqual(['onTrack'])
  })

  it('still reports "in progress" alongside a delivery verdict - the verdict must not count as a blocker', () => {
    const signals = summarize({
      lot: makeLot({
        source_item_id: null,
        input_demand_id: null,
        is_alteration: true,
        required_delivery_date: '2026-09-01',
      }),
      productionOrders: [
        makeOrder({
          lot_position_id: 1,
          status: 'in_progress',
          planned_end: '2026-08-20T12:00:00',
        }),
      ],
      today: '2026-08-05',
    })
    expect(signals.map((s) => s.id)).toEqual(['deliveryOnTrack', 'inProgress'])
  })

  it('reports "due", not "on track", for a lot with an unassigned position - and keeps notPlanned alongside it', () => {
    const signals = summarize({
      lot: makeLot({
        required_delivery_date: '2026-09-01',
        positions: [makePosition({ kind: 'unassigned' })],
      }),
      today: '2026-08-05',
    })
    expect(signals.map((s) => s.id)).toEqual(['deliveryDue', 'notPlanned'])
  })

  it('reports both the completed chip and a delivery verdict once a completion date is derivable', () => {
    const signals = summarize({
      lot: makeLot({ status: 'completed', required_delivery_date: '2026-08-01' }),
      productionOrders: [
        makeOrder({ lot_position_id: 1, status: 'completed', actual_end: '2026-08-10T12:00:00' }),
      ],
      today: '2026-08-05',
    })
    expect(signals.map((s) => s.id)).toEqual(['completed', 'deliveryCompletedLate'])
  })

  it('reports awaitingQa once every non-inspection position is done but the inspection is not', () => {
    const signals = summarize({
      lot: makeLot({
        source_item_id: null,
        input_demand_id: null,
        is_alteration: true,
        positions: [
          makePosition({
            id: 1,
            status: 'completed',
            steps: [makeFabricationStep({ position_id: 1 })],
          }),
          makePosition({
            id: 2,
            status: 'pending',
            steps: [makeInspectionStep({ position_id: 2 })],
          }),
        ],
      }),
    })
    expect(signals.map((s) => s.id)).toContain('awaitingQa')
  })

  it('does not report awaitingQa once the inspection position is also completed', () => {
    const signals = summarize({
      lot: makeLot({
        source_item_id: null,
        input_demand_id: null,
        is_alteration: true,
        positions: [
          makePosition({
            id: 1,
            status: 'completed',
            steps: [makeFabricationStep({ position_id: 1 })],
          }),
          makePosition({
            id: 2,
            status: 'completed',
            steps: [makeInspectionStep({ position_id: 2 })],
          }),
        ],
      }),
    })
    expect(signals.map((s) => s.id)).not.toContain('awaitingQa')
  })

  it('does not report awaitingQa for a lot with no inspection position at all', () => {
    const signals = summarize({
      lot: makeLot({
        source_item_id: null,
        input_demand_id: null,
        is_alteration: true,
        positions: [
          makePosition({
            id: 1,
            status: 'in_progress',
            steps: [makeFabricationStep({ position_id: 1 })],
          }),
        ],
      }),
    })
    expect(signals.map((s) => s.id)).not.toContain('awaitingQa')
  })

  it('does not report awaitingQa while other (non-inspection) positions are still unfinished', () => {
    const signals = summarize({
      lot: makeLot({
        source_item_id: null,
        input_demand_id: null,
        is_alteration: true,
        positions: [
          makePosition({
            id: 1,
            status: 'in_progress',
            steps: [makeFabricationStep({ position_id: 1 })],
          }),
          makePosition({
            id: 2,
            status: 'pending',
            steps: [makeInspectionStep({ position_id: 2 })],
          }),
        ],
      }),
    })
    expect(signals.map((s) => s.id)).not.toContain('awaitingQa')
  })
})
