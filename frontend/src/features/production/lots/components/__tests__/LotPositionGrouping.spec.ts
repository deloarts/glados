import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'


vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import LotPositionGrouping from '../LotPositionGrouping.vue'
import type { LotPositionResponse, LotStepResponse } from '../../../types/productionLotsResponse'
import { mountWithApp } from '@/test-utils/mountWithApp'

function makeStep(id: number, positionId: number, sequence: number): LotStepResponse {
  return {
    id,
    public_id: `00000000-0000-0000-0000-${String(id).padStart(12, '0')}`,
    created: '2026-07-01',
    note: null,
    estimated_setup_minutes: null,
    estimated_minutes_per_piece: null,
    time_budget_per_piece: null,
    sequence,
    creator_id: 1,
    fabrication_method_id: 1,
    role: 'fabrication' as const,
    inspection_method_id: null,
    inspection_method_name: null,
    inspection_method_requires_evidence: null,
    fabrication_method_name: { enGB: 'Milling' },
    fabrication_method_requires_machine: true,
    fabrication_method_required_external: false,
    fabrication_method_default_supplier_id: null,
    lot_id: 1,
    position_id: positionId,
    source_process_id: null,
  }
}

function makeInspectionStep(id: number, positionId: number, sequence: number): LotStepResponse {
  return {
    ...makeStep(id, positionId, sequence),
    fabrication_method_id: null,
    role: 'inspection' as const,
    inspection_method_id: 1,
    inspection_method_name: { enGB: 'Visual Inspection' },
    inspection_method_requires_evidence: false,
    fabrication_method_requires_machine: false,
  } as LotStepResponse
}

function makePosition(id: number, sequence: number, steps: LotStepResponse[]): LotPositionResponse {
  return {
    id,
    public_id: `22222222-2222-2222-2222-${String(id).padStart(12, '0')}`,
    created: '2026-07-01',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    sequence,
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

describe('LotPositionGrouping', () => {
  it('renders without errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const step1 = makeStep(1, 1, 1)
    const step2 = makeStep(2, 2, 2)
    const positions = [makePosition(1, 1, [step1]), makePosition(2, 2, [step2])]

    const wrapper = mountWithApp(LotPositionGrouping, {
      attachTo: document.body,
      props: { lotId: 1, steps: [step1, step2], positions, readonly: false },
    })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    wrapper.unmount()
  })

  it('excludes an inspection step from grouping - no toggle on either side of it', async () => {
    const step1 = makeStep(1, 1, 1)
    const step2 = makeInspectionStep(2, 2, 2)
    const step3 = makeStep(3, 3, 3)
    const positions = [makePosition(1, 1, [step1]), makePosition(2, 2, [step2]), makePosition(3, 3, [step3])]

    const wrapper = mountWithApp(LotPositionGrouping, {
      attachTo: document.body,
      props: { lotId: 1, steps: [step1, step2, step3], positions, readonly: false },
    })

    await flushPromises()
    await flushPromises()

    // Both neighbours of the inspection are separated by a plain marker,
    // leaving no toggle anywhere in this chain.
    expect(wrapper.findAll('.boundary-toggle')).toHaveLength(0)
    expect(wrapper.findAll('.boundary-fixed')).toHaveLength(2)
    expect(wrapper.findAll('.step-chip--standalone')).toHaveLength(1)

    wrapper.unmount()
  })
})
