import { describe, it, expect } from 'vitest'

import { buildAssignTargetGroups, parseAssignTargetKey } from '../lotStepAssignOptions'
import { makePosition } from '../../__tests__/fixtures'

import type { ProductionMachineResponse, MachinePoolResponse } from '@/features/production-machines'
import type { OrderResponse } from '@/features/orders'
import type { LotStepResponse } from '../../../types/productionLotsResponse'

// Covers the group/permission/QA rules in isolation, before LotStepList.vue
// wires the util into the Machine / Order column's Select.

const MACHINE: ProductionMachineResponse = {
  id: 1,
  public_id: '66666666-6666-6666-6666-666666666666',
  archived: false,
  created: '2026-07-01',
  changed: null,
  changed_by_id: null,
  changed_by_full_name: '',
  internal_name: 'Machine 1',
  vendor: 'Acme',
  model: 'M100',
  fabrication_method_ids: [1],
  fabrication_methods: [],
  max_part_dimension: null,
  is_qa_machine: false,
  note: null,
  creator_id: 1,
  creator_full_name: 'Alice',
  changes: [],
  active_orders: [],
  live_order_count: 0,
  open_downtime: null,
  status: 'down',
}

const QA_MACHINE: ProductionMachineResponse = {
  ...MACHINE,
  id: 2,
  public_id: '88888888-8888-8888-8888-888888888888',
  internal_name: 'QA Machine 1',
  fabrication_method_ids: [],
  is_qa_machine: true,
}

// Covers fabrication method 1 (MACHINE's): the pools-group option.
const POOL: MachinePoolResponse = {
  id: 9,
  public_id: '77777777-7777-7777-7777-777777777777',
  archived: false,
  created: '2026-07-01',
  changed: null,
  changed_by_id: null,
  changed_by_full_name: '',
  name: 'Mill Pool',
  machine_ids: [1],
  machines: [MACHINE],
  note: null,
  creator_id: 1,
  creator_full_name: 'Alice',
  changes: [],
}

const ORDER = {
  id: 100,
  order_number: 'PO-2026-0100',
  supplier_name: 'Acme Supply',
  status: 'draft',
} as unknown as OrderResponse

const fabricationStep: LotStepResponse = {
  id: 1,
  public_id: '11111111-1111-1111-1111-111111111111',
  created: '2026-07-01',
  note: null,
  estimated_setup_minutes: 10,
  estimated_minutes_per_piece: 2,
  time_budget_per_piece: null,
  sequence: 1,
  creator_id: 1,
  fabrication_method_id: 1,
  role: 'fabrication',
  inspection_method_id: null,
  inspection_method_name: null,
  inspection_method_requires_evidence: null,
  fabrication_method_name: { enGB: 'Milling' },
  fabrication_method_requires_machine: true,
  fabrication_method_required_external: false,
  fabrication_method_default_supplier_id: null,
  lot_id: 1,
  position_id: 1,
  source_process_id: null,
}

const manualStep: LotStepResponse = {
  ...fabricationStep,
  id: 2,
  fabrication_method_id: 3,
  fabrication_method_name: { enGB: 'Deburring' },
  fabrication_method_requires_machine: false,
}

const inspectionStep: LotStepResponse = {
  id: 3,
  public_id: '22222222-2222-2222-2222-222222222222',
  created: '2026-07-01',
  note: null,
  estimated_setup_minutes: null,
  estimated_minutes_per_piece: null,
  time_budget_per_piece: null,
  sequence: 1,
  creator_id: 1,
  fabrication_method_id: null,
  role: 'inspection',
  inspection_method_id: 5,
  inspection_method_name: { enGB: 'Visual Inspection' },
  inspection_method_requires_evidence: false,
  fabrication_method_name: { enGB: '' },
  fabrication_method_requires_machine: false,
  fabrication_method_default_supplier_id: null,
  fabrication_method_required_external: false,
  lot_id: 1,
  position_id: 2,
  source_process_id: null,
}

const machineRequiringPosition = makePosition({ steps: [fabricationStep] })
const qaPosition = makePosition({ id: 2, steps: [inspectionStep] })
const manualPosition = makePosition({ id: 3, steps: [manualStep] })

const labels = {
  pools: 'Pools',
  machines: 'Machines',
  manual: 'Manual',
  orders: 'Orders',
  create: 'Create',
  queueWithoutMachine: 'Queue without machine',
  createOrder: 'Create order…',
}

describe('buildAssignTargetGroups', () => {
  it('groups a machine-requiring fabrication position as Pools, Machines, Orders, Create - in that order, QA machine excluded', () => {
    const groups = buildAssignTargetGroups({
      position: machineRequiringPosition,
      machines: [MACHINE, QA_MACHINE],
      pools: [POOL],
      orders: [ORDER],
      canAssignInternal: true,
      canAssignExternal: true,
      labels,
    })

    expect(groups.map((g) => g.key)).toEqual(['pools', 'machines', 'orders', 'create'])
    expect(groups.find((g) => g.key === 'pools')!.items).toEqual([{ key: 'pool:9', label: 'Mill Pool' }])
    expect(groups.find((g) => g.key === 'machines')!.items).toEqual([
      { key: 'machine:1', label: 'Machine 1' },
    ])
    expect(groups.find((g) => g.key === 'orders')!.items).toEqual([
      { key: 'order:100', label: 'PO-2026-0100 · Acme Supply' },
    ])
    expect(groups.find((g) => g.key === 'create')!.items).toEqual([
      { key: 'order:new', label: 'Create order…' },
    ])
  })

  it('offers only QA machines for a QA position - no pools/manual/orders/create even with both permissions', () => {
    const groups = buildAssignTargetGroups({
      position: qaPosition,
      machines: [MACHINE, QA_MACHINE],
      pools: [POOL],
      orders: [ORDER],
      canAssignInternal: true,
      canAssignExternal: true,
      labels,
    })

    expect(groups.map((g) => g.key)).toEqual(['machines'])
    expect(groups[0]!.items).toEqual([{ key: 'machine:2', label: 'QA Machine 1' }])
  })

  it('offers Manual, Orders, Create for a manual-only position - no machines/pools', () => {
    const groups = buildAssignTargetGroups({
      position: manualPosition,
      machines: [MACHINE],
      pools: [POOL],
      orders: [ORDER],
      canAssignInternal: true,
      canAssignExternal: true,
      labels,
    })

    expect(groups.map((g) => g.key)).toEqual(['manual', 'orders', 'create'])
    expect(groups.find((g) => g.key === 'manual')!.items).toEqual([
      { key: 'manual', label: 'Queue without machine' },
    ])
  })

  it('hides Pools/Machines/Manual when canAssignInternal is false', () => {
    const groups = buildAssignTargetGroups({
      position: manualPosition,
      machines: [MACHINE],
      pools: [POOL],
      orders: [ORDER],
      canAssignInternal: false,
      canAssignExternal: true,
      labels,
    })

    expect(groups.map((g) => g.key)).toEqual(['orders', 'create'])
  })

  it('hides Orders/Create when canAssignExternal is false', () => {
    const groups = buildAssignTargetGroups({
      position: machineRequiringPosition,
      machines: [MACHINE],
      pools: [POOL],
      orders: [ORDER],
      canAssignInternal: true,
      canAssignExternal: false,
      labels,
    })

    expect(groups.map((g) => g.key)).toEqual(['pools', 'machines'])
  })

  it('omits the Orders group when there are no open orders but still shows Create', () => {
    const groups = buildAssignTargetGroups({
      position: machineRequiringPosition,
      machines: [],
      pools: [],
      orders: [],
      canAssignInternal: false,
      canAssignExternal: true,
      labels,
    })

    expect(groups.map((g) => g.key)).toEqual(['create'])
  })
})

describe('parseAssignTargetKey', () => {
  it('round-trips every key kind', () => {
    expect(parseAssignTargetKey('pool:9')).toEqual({ kind: 'pool', id: 9 })
    expect(parseAssignTargetKey('machine:1')).toEqual({ kind: 'machine', id: 1 })
    expect(parseAssignTargetKey('order:100')).toEqual({ kind: 'order', id: 100 })
    expect(parseAssignTargetKey('manual')).toEqual({ kind: 'manual' })
    expect(parseAssignTargetKey('order:new')).toEqual({ kind: 'create' })
  })

  it('returns null for garbage', () => {
    expect(parseAssignTargetKey('garbage')).toBeNull()
    expect(parseAssignTargetKey('order:abc')).toBeNull()
    expect(parseAssignTargetKey('pool:')).toBeNull()
    expect(parseAssignTargetKey('')).toBeNull()
  })
})
