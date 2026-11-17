import { createPinia, setActivePinia } from 'pinia'
import { describe, it, expect, beforeEach } from 'vitest'

import { pseudoPosition, stepIcon, stepMethodLabel, stepLabel, INSPECTION_ICON } from '../lotStepDisplay'

import type { LotSummaryResponse, LotSummaryStepResponse } from '../../types/productionLotsResponse'

const BASE = {
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
  position_kind: 'internal' as const,
  position_needs_machine: true,
  position_status: 'pending' as const,
  position_quantity: 10,
  position_quantity_remaining: 10,
}

function makeFabricationStep(
  overrides: Partial<LotSummaryStepResponse> = {},
): LotSummaryStepResponse {
  return {
    ...BASE,
    role: 'fabrication',
    fabrication_method_id: 5,
    fabrication_method_name: 'Milling',
    fabrication_method_requires_machine: true,
    inspection_method_id: null,
    inspection_method_name: null,
    inspection_method_requires_evidence: null,
    ...overrides,
  } as LotSummaryStepResponse
}

function makeInspectionStep(
  overrides: Partial<LotSummaryStepResponse> = {},
): LotSummaryStepResponse {
  return {
    ...BASE,
    role: 'inspection',
    fabrication_method_id: null,
    fabrication_method_name: '',
    fabrication_method_requires_machine: false,
    inspection_method_id: 5,
    inspection_method_name: 'Measurement',
    inspection_method_requires_evidence: true,
    ...overrides,
  } as LotSummaryStepResponse
}

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('stepIcon', () => {
  it('renders the QA icon for an inspection step regardless of its position kind', () => {
    expect(stepIcon(makeInspectionStep({ position_kind: 'internal' }))).toBe(INSPECTION_ICON)
    expect(stepIcon(makeInspectionStep({ position_kind: 'external' }))).toBe(INSPECTION_ICON)
    expect(stepIcon(makeInspectionStep({ position_kind: 'mixed' }))).toBe(INSPECTION_ICON)
  })

  it('renders the position-kind icon for a fabrication step', () => {
    expect(stepIcon(makeFabricationStep({ position_kind: 'internal' }))).toBe('mdi mdi-factory')
    expect(stepIcon(makeFabricationStep({ position_kind: 'external' }))).toBe('mdi mdi-cart')
  })
})

describe('stepMethodLabel', () => {
  it("shows a fabrication step's own method name", () => {
    expect(stepMethodLabel(makeFabricationStep({ fabrication_method_name: { enGB: 'Milling' } }))).toBe(
      'Milling',
    )
  })

  it("shows just the inspection method's own name for an inspection step, never a fabrication method name or a QA prefix", () => {
    expect(stepMethodLabel(makeInspectionStep({ inspection_method_name: { enGB: 'Measurement' } }))).toBe(
      'Measurement',
    )
    expect(stepMethodLabel(makeInspectionStep({ inspection_method_name: { enGB: 'Visual Inspection' } }))).toBe(
      'Visual Inspection',
    )
  })
})

describe('pseudoPosition', () => {
  const lot: LotSummaryResponse = {
    edit_version: 0,
    id: 1,
    public_id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
    lot_number: 'LOT-1',
    quantity: 10,
    quantity_completed: 0,
    status: 'draft',
    priority: 'normal',
    created: '2026-08-01T09:00:00',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    required_delivery_date: null,
    made_item_id: 1,
    made_item_part_number: 'PN-1',
    made_item_article_name: 'Bracket',
    made_item_revision: 'A',
    made_item_material: '1.0037',
    source_bought_item_id: null,
    source_item_id: null,
    source_made_item_id: null,
    source_label: '',
    source_sublabel: '',
    source_material: '',
    demand_status: '',
    is_alteration: false,
    project_id: 1,
    project_number: 'P-001',
    project_customer: 'Acme',
    creator_id: 1,
    creator: null,
    input_demand_id: null,
    source_approval_status: 'not_required',
    positions: [],
    steps: [
      makeFabricationStep({ id: 1, position_id: 1 }),
      makeFabricationStep({ id: 2, position_id: 2 }),
      makeInspectionStep({ id: 3, position_id: 1 }),
    ],
    actions: [],
    blocked_actions: {},
    completed_at: null,
    origin_disposition: null,
    origin_lot_id: null,
    source_approved_by_id: null,
    source_approved_date: null,
    source_delivery_date: null,
    source_expected_delivery_date: null,
    source_order_id: null,
    source_order_number: null,
    source_rejected_by_id: null,
    source_rejected_date: null,
    source_rejection_reason: null,
    target_date: null,
    target_date_demand_item_id: null,
    target_date_source: null,
  }

  it('builds a position-shaped object from only the steps matching positionId', () => {
    const position = pseudoPosition(lot, 1)
    expect(position.steps.map((s) => s.id)).toEqual([1, 3])
  })

  it('returns only a steps field - no position-level fields (kind, quantity, ...) leak through', () => {
    const position = pseudoPosition(lot, 1)
    expect(Object.keys(position)).toEqual(['steps'])
  })

  it('returns an empty steps array when no step matches the position id', () => {
    expect(pseudoPosition(lot, 999).steps).toEqual([])
  })
})

describe('stepLabel', () => {
  it('appends the allocated/total split only when partially allocated', () => {
    const fullyOpen = makeFabricationStep({ position_quantity: 10, position_quantity_remaining: 10 })
    expect(stepLabel(fullyOpen)).toBe('Milling')

    const partial = makeFabricationStep({ position_quantity: 10, position_quantity_remaining: 4 })
    expect(stepLabel(partial)).toBe('Milling (6/10)')

    const fullyAllocated = makeFabricationStep({
      position_quantity: 10,
      position_quantity_remaining: 0,
    })
    expect(stepLabel(fullyAllocated)).toBe('Milling')
  })

  it('applies the same allocation split logic to an inspection step, never a raw method name', () => {
    const partial = makeInspectionStep({
      inspection_method_name: { enGB: 'Visual Inspection' },
      position_quantity: 8,
      position_quantity_remaining: 3,
    })
    expect(stepLabel(partial)).toBe('Visual Inspection (5/8)')
  })
})
