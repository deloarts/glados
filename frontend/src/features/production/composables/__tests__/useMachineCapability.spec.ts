import { describe, expect, it } from 'vitest'

import { useMachineCapability } from '../useMachineCapability'

import type { MachinePoolResponse } from '@/features/production-machines'
import type { ProductionMachineResponse } from '@/features/production-machines'
import type {
  FabricationLotStep,
  InspectionLotStep,
  LotPositionResponse,
  LotStepResponse,
} from '../../types/productionLotsResponse'

function makeFabricationStep(): FabricationLotStep {
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
  }
}

function makeManualStep(overrides: Partial<FabricationLotStep> = {}): FabricationLotStep {
  return {
    ...makeFabricationStep(),
    id: 3,
    fabrication_method_name: { enGB: 'Cutting' },
    fabrication_method_requires_machine: false,
    fabrication_method_id: 2,
    ...overrides,
  }
}

function makeInspectionStep(): InspectionLotStep {
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

function makeMachine(overrides: Partial<ProductionMachineResponse> = {}): ProductionMachineResponse {
  return {
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
    ...overrides,
  }
}

describe('useMachineCapability QA gate', () => {
  const { getCapableMachines, machineCoversPosition, poolCoversPosition } = useMachineCapability()

  it('offers only QA machines for an inspection position', () => {
    const machines = [
      makeMachine({ id: 1 }),
      makeMachine({ id: 2, is_qa_machine: true, fabrication_method_ids: [] }),
    ]
    const capable = getCapableMachines(makePosition([makeInspectionStep()]), machines)
    expect(capable.map((m) => m.id)).toEqual([2])
  })

  it('never offers a QA machine for a fabrication position, even with matching methods', () => {
    const machines = [
      makeMachine({ id: 1 }),
      makeMachine({ id: 2, is_qa_machine: true, fabrication_method_ids: [1] }),
    ]
    const capable = getCapableMachines(makePosition([makeFabricationStep()]), machines)
    expect(capable.map((m) => m.id)).toEqual([1])
  })

  it('machineCoversPosition mirrors the same gate in both directions', () => {
    const qaPosition = makePosition([makeInspectionStep()])
    const fabricationPosition = makePosition([makeFabricationStep()])
    const qaMachine = makeMachine({ id: 2, is_qa_machine: true, fabrication_method_ids: [1] })
    expect(machineCoversPosition(qaPosition, qaMachine)).toBe(true)
    expect(machineCoversPosition(qaPosition, makeMachine())).toBe(false)
    expect(machineCoversPosition(fabricationPosition, qaMachine)).toBe(false)
    expect(machineCoversPosition(fabricationPosition, makeMachine())).toBe(true)
  })

  it('an inspection position is never covered by a pool', () => {
    const pool: MachinePoolResponse = {
      id: 1,
      public_id: '44444444-4444-4444-4444-444444444444',
      archived: false,
      created: '2026-08-01',
      changed: null,
      changed_by_id: null,
      changed_by_full_name: '',
      name: 'Mills',
      machine_ids: [1],
      machines: [makeMachine()],
      note: null,
      creator_id: 1,
      creator_full_name: 'Tester',
      changes: [],
    }
    expect(poolCoversPosition(makePosition([makeInspectionStep()]), pool)).toBe(false)
  })
})

describe('useMachineCapability pure-manual positions', () => {
  const { positionIsManual, machineCoversPosition, poolCoversPosition, getCapableMachines } =
    useMachineCapability()

  it('positionIsManual is true only when every step skips the machine', () => {
    expect(positionIsManual(makePosition([makeManualStep()]))).toBe(true)
    expect(positionIsManual(makePosition([makeManualStep(), makeFabricationStep()]))).toBe(false)
    expect(positionIsManual(makePosition([]))).toBe(false)
  })

  it('no machine covers a pure-manual position, even one with an empty capability list', () => {
    // An empty required-method set is vacuously satisfied by every
    // machine's `.every()` check, so without a guard "cutting to length" would
    // read as assignable to any machine, including one that can do
    // nothing at all.
    const position = makePosition([makeManualStep()])
    expect(machineCoversPosition(position, makeMachine({ fabrication_method_ids: [] }))).toBe(
      false,
    )
    expect(machineCoversPosition(position, makeMachine({ fabrication_method_ids: [1] }))).toBe(
      false,
    )
  })

  it('no pool covers a pure-manual position', () => {
    const pool: MachinePoolResponse = {
      id: 1,
      public_id: '44444444-4444-4444-4444-444444444444',
      archived: false,
      created: '2026-08-01',
      changed: null,
      changed_by_id: null,
      changed_by_full_name: '',
      name: 'Mills',
      machine_ids: [1],
      machines: [makeMachine()],
      note: null,
      creator_id: 1,
      creator_full_name: 'Tester',
      changes: [],
    }
    expect(poolCoversPosition(makePosition([makeManualStep()]), pool)).toBe(false)
  })

  it('getCapableMachines offers nothing for a pure-manual position', () => {
    const machines = [makeMachine({ id: 1 }), makeMachine({ id: 2, fabrication_method_ids: [] })]
    expect(getCapableMachines(makePosition([makeManualStep()]), machines)).toEqual([])
  })

  it('a mixed position still ignores the manual step, unaffected by the pure-manual guard', () => {
    const position = makePosition([makeManualStep(), makeFabricationStep()])
    expect(machineCoversPosition(position, makeMachine({ fabrication_method_ids: [1] }))).toBe(
      true,
    )
  })
})

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

describe('useMachineCapability auto-pool', () => {
  const { candidatePoolsForPosition, autoPoolForPosition } = useMachineCapability()

  it('candidatePoolsForPosition keeps only pools covering every required method', () => {
    const position = makePosition([makeFabricationStep()]) // requires method 1
    const covering = makePool({ id: 1, machines: [makeMachine({ fabrication_method_ids: [1, 2] })] })
    const notCovering = makePool({ id: 2, machines: [makeMachine({ fabrication_method_ids: [2] })] })

    expect(candidatePoolsForPosition(position, [covering, notCovering]).map((p) => p.id)).toEqual([
      1,
    ])
  })

  it('picks the most specialized pool first (fewest methods in its own capability)', () => {
    const position = makePosition([makeFabricationStep()]) // requires method 1
    // Both cover method 1, but the "generalist" pool's intersection also
    // includes method 2 (a second machine that happens to share method 1),
    // while the "specialist" pool's intersection is method 1 alone.
    const specialist = makePool({
      id: 1,
      machines: [
        makeMachine({ id: 10, fabrication_method_ids: [1] }),
        makeMachine({ id: 11, fabrication_method_ids: [1] }),
      ],
    })
    const generalist = makePool({
      id: 2,
      machines: [makeMachine({ id: 12, fabrication_method_ids: [1, 2] })],
    })

    expect(autoPoolForPosition(position, [generalist, specialist])?.id).toBe(1)
  })

  it('breaks a capability tie by fewest member machines', () => {
    const position = makePosition([makeFabricationStep()])
    const smaller = makePool({
      id: 1,
      machines: [makeMachine({ id: 10, fabrication_method_ids: [1] })],
    })
    const bigger = makePool({
      id: 2,
      machines: [
        makeMachine({ id: 11, fabrication_method_ids: [1] }),
        makeMachine({ id: 12, fabrication_method_ids: [1] }),
      ],
    })

    expect(autoPoolForPosition(position, [bigger, smaller])?.id).toBe(1)
  })

  it('breaks a full tie by lowest pool id', () => {
    const position = makePosition([makeFabricationStep()])
    const machine = () => makeMachine({ fabrication_method_ids: [1] })
    const poolA = makePool({ id: 5, machines: [machine()] })
    const poolB = makePool({ id: 2, machines: [machine()] })

    expect(autoPoolForPosition(position, [poolA, poolB])?.id).toBe(2)
  })

  it('returns null when no pool covers the position', () => {
    const position = makePosition([makeFabricationStep()])
    const notCovering = makePool({ machines: [makeMachine({ fabrication_method_ids: [2] })] })

    expect(autoPoolForPosition(position, [notCovering])).toBeNull()
  })

  it('never auto-picks a pool for a QA/inspection position', () => {
    const position = makePosition([makeInspectionStep()])
    const pool = makePool({ machines: [makeMachine()] })

    expect(autoPoolForPosition(position, [pool])).toBeNull()
  })
})
