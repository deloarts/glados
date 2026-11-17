import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it, beforeEach } from 'vitest'

import { useLotPositionAssignmentHelpers } from '../useLotPositionAssignmentHelpers'

import type { MachinePoolResponse } from '@/features/production-machines'
import type {
  FabricationLotStep,
  InspectionLotStep,
  LotPositionResponse,
  LotStepResponse,
} from '../../../types/productionLotsResponse'

function makeFabricationStep(overrides: Partial<FabricationLotStep> = {}): FabricationLotStep {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-08-01T00:00:00Z',
    note: null,
    estimated_setup_minutes: null,
    estimated_minutes_per_piece: null,
    time_budget_per_piece: null,
    sequence: 1,
    creator_id: 1,
    fabrication_method_name: { enGB: 'Milling' },
    fabrication_method_requires_machine: true,
    fabrication_method_required_external: false,
    fabrication_method_default_supplier_id: null,
    lot_id: 1,
    position_id: 1,
    source_process_id: null,
    role: 'fabrication',
    fabrication_method_id: 1,
    inspection_method_id: null,
    inspection_method_name: null,
    inspection_method_requires_evidence: null,
    ...overrides,
  }
}

function makeInspectionStep(overrides: Partial<InspectionLotStep> = {}): InspectionLotStep {
  return {
    id: 2,
    public_id: '11111111-1111-1111-1111-111111111112',
    created: '2026-08-01T00:00:00Z',
    note: null,
    estimated_setup_minutes: null,
    estimated_minutes_per_piece: null,
    time_budget_per_piece: null,
    sequence: 2,
    creator_id: 1,
    fabrication_method_name: { enGB: '' },
    fabrication_method_requires_machine: false,
    fabrication_method_required_external: false,
    fabrication_method_default_supplier_id: null,
    lot_id: 1,
    position_id: 1,
    source_process_id: null,
    role: 'inspection',
    fabrication_method_id: null,
    inspection_method_id: 1,
    inspection_method_name: { enGB: 'Measurement' },
    inspection_method_requires_evidence: true,
    ...overrides,
  }
}

function makePosition(steps: LotStepResponse[]): LotPositionResponse {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    created: '2026-08-01T00:00:00Z',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    sequence: 1,
    kind: 'unassigned',
    status: 'pending',
    quantity: 5,
    quantity_completed: 0,
    quantity_remaining: 5,
    note: null,
    creator_id: 1,
    lot_id: 1,
    steps,
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
  }
}

function makePool(overrides: Partial<MachinePoolResponse> = {}): MachinePoolResponse {
  return {
    id: 1,
    public_id: '55555555-5555-5555-5555-555555555555',
    archived: false,
    created: '2026-08-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    name: 'Pool',
    machine_ids: [],
    machines: [],
    note: null,
    creator_id: 1,
    creator_full_name: 'Tester',
    changes: [],
    ...overrides,
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('useLotPositionAssignmentHelpers sortedSteps', () => {
  it('sorts a position steps by sequence, independent of input order', () => {
    const { sortedSteps } = useLotPositionAssignmentHelpers(ref([]))
    const first = makeFabricationStep({ id: 1, sequence: 1 })
    const second = makeFabricationStep({ id: 2, sequence: 2 })
    const position = makePosition([second, first])

    expect(sortedSteps(position).map((s) => s.id)).toEqual([1, 2])
  })
})

describe('useLotPositionAssignmentHelpers positionRequiresMachineAssignment', () => {
  it('is true for an inspection (QA) position', () => {
    const { positionRequiresMachineAssignment } = useLotPositionAssignmentHelpers(ref([]))
    expect(positionRequiresMachineAssignment(makePosition([makeInspectionStep()]))).toBe(true)
  })

  it('is true for a fabrication position with a machine-requiring method', () => {
    const { positionRequiresMachineAssignment } = useLotPositionAssignmentHelpers(ref([]))
    expect(positionRequiresMachineAssignment(makePosition([makeFabricationStep()]))).toBe(true)
  })

  it('is false for a manual-only position (no machine-requiring step)', () => {
    const { positionRequiresMachineAssignment } = useLotPositionAssignmentHelpers(ref([]))
    const manualStep = makeFabricationStep({ fabrication_method_requires_machine: false })
    expect(positionRequiresMachineAssignment(makePosition([manualStep]))).toBe(false)
  })
})

describe('useLotPositionAssignmentHelpers resolvedPoolFor', () => {
  it('reads the pools ref reactively, resolving the covering pool for a position', () => {
    const pools = ref<MachinePoolResponse[]>([])
    const { resolvedPoolFor } = useLotPositionAssignmentHelpers(pools)
    const position = makePosition([makeFabricationStep()]) // requires method 1

    expect(resolvedPoolFor(position)).toBeNull()

    // A pool whose member machine covers method 1 becomes resolvable once
    // the caller's pools ref is populated (e.g. after loadPools() resolves).
    pools.value = [
      makePool({
        id: 7,
        machines: [
          {
            id: 1,
            public_id: '33333333-3333-3333-3333-333333333333',
            archived: false,
            created: '2026-08-01',
            changed: null,
            changed_by_id: null,
            changed_by_full_name: '',
            internal_name: 'CNC1',
            vendor: 'Contoso',
            model: 'VF-2',
            fabrication_method_ids: [1],
            fabrication_methods: [],
            max_part_dimension: null,
            note: null,
            is_qa_machine: false,
            creator_id: 1,
            creator_full_name: 'Tester',
            changes: [],
            active_orders: [],
            live_order_count: 0,
            open_downtime: null,
            status: 'down',
          },
        ],
      }),
    ]

    expect(resolvedPoolFor(position)?.id).toBe(7)
  })

  it('returns null for a QA position, mirroring autoPoolForPosition', () => {
    const pools = ref<MachinePoolResponse[]>([makePool({ id: 1 })])
    const { resolvedPoolFor } = useLotPositionAssignmentHelpers(pools)
    expect(resolvedPoolFor(makePosition([makeInspectionStep()]))).toBeNull()
  })
})

describe('useLotPositionAssignmentHelpers uncoveredMethodNames', () => {
  it('returns the inspection method names for a QA position', () => {
    const { uncoveredMethodNames } = useLotPositionAssignmentHelpers(ref([]))
    const position = makePosition([makeInspectionStep({ inspection_method_name: { enGB: 'Measurement' } })])
    expect(uncoveredMethodNames(position)).toEqual(['Measurement'])
  })

  it('returns the machine-requiring fabrication method names for a fabrication position', () => {
    const { uncoveredMethodNames } = useLotPositionAssignmentHelpers(ref([]))
    const machineStep = makeFabricationStep({ fabrication_method_id: 1, fabrication_method_name: { enGB: 'Milling' } })
    const manualStep = makeFabricationStep({
      id: 3,
      fabrication_method_id: 2,
      fabrication_method_name: { enGB: 'Deburring' },
      fabrication_method_requires_machine: false,
    })
    const position = makePosition([machineStep, manualStep])
    expect(uncoveredMethodNames(position)).toEqual(['Milling'])
  })

  it('dedupes repeated method names', () => {
    const { uncoveredMethodNames } = useLotPositionAssignmentHelpers(ref([]))
    const stepA = makeFabricationStep({ id: 1, fabrication_method_id: 1, fabrication_method_name: { enGB: 'Milling' } })
    const stepB = makeFabricationStep({ id: 3, fabrication_method_id: 1, fabrication_method_name: { enGB: 'Milling' } })
    const position = makePosition([stepA, stepB])
    expect(uncoveredMethodNames(position)).toEqual(['Milling'])
  })
})
