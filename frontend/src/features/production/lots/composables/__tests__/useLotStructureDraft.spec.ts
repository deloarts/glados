import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { createPinia, setActivePinia, storeToRefs } from 'pinia'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeLotResponse } from '@/test-utils/factories'

// Same style as useErrorToast.spec.ts: the composable calls useToast()
// itself (see save()'s failSave), so the toast is asserted by mocking the
// plugin's own hook rather than hunting a rendered .p-toast-message.
const toastAddMock = vi.fn<(message: unknown) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>(() =>
  Promise.resolve({ data: [] }),
)
const postMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>(() =>
  Promise.resolve({ data: {} }),
)

// Mutated mid-test (directly, or from a putMock override) so a refetch
// triggered by save() itself (after the structure PUT, after a successful
// assign/reassign) can hand back a DIFFERENT lot than the one the draft
// started from, same as the real backend would.
let currentLotResponse: unknown = null

const getMock = vi.fn<(url: string) => Promise<unknown>>((url: string) => {
  if (/^\/production-lots\/\d+$/.test(url)) return Promise.resolve({ data: currentLotResponse })
  return Promise.resolve({ data: { items: [], total: 0, limit: 1000, skip: 0 } })
})

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    post: (url: string, payload: unknown) => postMock(url, payload),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import { useLotStructureDraft } from '../useLotStructureDraft'
import { useProductionLotDetailStore } from '../../stores/productionLotDetailStore'
import { useProductionQueueStore } from '../../../stores/productionQueueStore'
import type {
  LotPositionProductionOrderSummary,
  LotPositionResponse,
  LotResponse,
  LotStepResponse,
} from '../../../types/productionLotsResponse'

function makeStep(overrides: Partial<LotStepResponse> = {}): LotStepResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-08-01T09:00:00',
    note: null,
    estimated_setup_minutes: null,
    estimated_minutes_per_piece: null,
    time_budget_per_piece: null,
    sequence: 1,
    creator_id: 1,
    fabrication_method_id: 1,
    fabrication_method_name: 'Milling',
    fabrication_method_requires_machine: true,
    fabrication_method_required_external: false,
    fabrication_method_default_supplier_id: null,
    lot_id: 1,
    position_id: 1,
    source_process_id: null,
    role: 'fabrication',
    inspection_method_id: null,
    inspection_method_name: null,
    inspection_method_requires_evidence: null,
    ...overrides,
  } as LotStepResponse
}

function makeOrder(
  overrides: Partial<LotPositionProductionOrderSummary> = {},
): LotPositionProductionOrderSummary {
  return {
    id: 10,
    production_order_number: 'PO-0010',
    edit_version: 0,
    status: 'queued',
    priority: 'normal',
    quantity: 5,
    quantity_completed: 0,
    machine_id: 1,
    machine_internal_name: 'Machine 1',
    machine_pool_id: null,
    machine_pool_name: '',
    conflicts: [],
    ...overrides,
  }
}

function makePosition(overrides: Partial<LotPositionResponse> = {}): LotPositionResponse {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    created: '2026-08-01T09:00:00',
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
    steps: [makeStep()],
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

function makeLot(overrides: Partial<LotResponse> = {}): LotResponse {
  return makeLotResponse({
    created: '2026-08-01',
    lot_number: 'LN-26-00001',
    quantity: 5,
    quantity_completed: 0,
    status: 'draft',
    project_id: 7,
    project_number: 'P-007',
    positions: [makePosition()],
    ...overrides,
  })
}

// Drives the composable inside a tiny host component (mounted with pinia +
// OpenVue + i18n via mountWithApp), same technique useErrorToast.spec.ts
// uses for its own composable-only spec. `result` is captured out of
// setup() since useLotStructureDraft isn't itself a component.
function mountDraft(initialLot: LotResponse | null) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const detailStore = useProductionLotDetailStore()
  if (initialLot) detailStore.lot = initialLot

  let result!: ReturnType<typeof useLotStructureDraft>
  const wrapper = mountWithApp(
    defineComponent({
      setup() {
        const { lot } = storeToRefs(useProductionLotDetailStore())
        result = useLotStructureDraft(lot)
        return () => h('div')
      },
    }),
    { pinia },
  )
  return { wrapper, result, detailStore, queueStore: useProductionQueueStore() }
}

describe('useLotStructureDraft staged assignment (Revision 2)', () => {
  beforeEach(() => {
    putMock.mockClear()
    postMock.mockClear()
    getMock.mockClear()
    toastAddMock.mockClear()
    currentLotResponse = null
  })

  it('staging an assignment marks the draft dirty; reset discards it', async () => {
    const lot = makeLot()
    const { result, wrapper } = mountDraft(lot)
    await flushPromises()

    expect(result.isDirty.value).toBe(false)

    result.assignPosition(1, 'machine:5')
    await flushPromises()

    expect(result.isDirty.value).toBe(true)
    expect(result.pendingAssignments.value).toEqual({ 1: 'machine:5' })

    result.reset()
    await flushPromises()

    expect(result.isDirty.value).toBe(false)
    expect(result.pendingAssignments.value).toEqual({})

    wrapper.unmount()
  })

  it('appendStep builds a fully-shaped step object for each role', async () => {
    const lot = makeLot({ positions: [makePosition({ id: 1 })] })
    const { result, wrapper } = mountDraft(lot)
    await flushPromises()

    result.appendStep({ role: 'fabrication', fabrication_method_id: 7 })
    await flushPromises()
    const fabricationStep = result.draftSteps.value.find(
      (s) => s.role === 'fabrication' && s.fabrication_method_id === 7,
    )
    expect(fabricationStep).toMatchObject({
      role: 'fabrication',
      fabrication_method_id: 7,
      inspection_method_id: null,
      inspection_method_name: null,
      inspection_method_requires_evidence: null,
      fabrication_method_name: {},
      fabrication_method_required_external: false,
      fabrication_method_default_supplier_id: null,
    })

    result.appendStep({ role: 'inspection', inspection_method_id: 9 })
    await flushPromises()
    const inspectionStep = result.draftSteps.value.find(
      (s) => s.role === 'inspection' && s.inspection_method_id === 9,
    )
    expect(inspectionStep).toMatchObject({
      role: 'inspection',
      inspection_method_id: 9,
      inspection_method_name: {},
      inspection_method_requires_evidence: false,
      fabrication_method_id: null,
      fabrication_method_requires_machine: false,
    })

    wrapper.unmount()
  })

  it('save with a clean structure skips the structure PUT and assigns with the saved quantity_remaining', async () => {
    const lot = makeLot({ positions: [makePosition({ id: 1, quantity_remaining: 3 })] })
    currentLotResponse = lot
    const { result, wrapper } = mountDraft(lot)
    await flushPromises()

    result.assignPosition(1, 'machine:5')
    await flushPromises()

    const succeeded = await result.save(1)
    await flushPromises()

    expect(succeeded).toBe(true)
    expect(putMock).not.toHaveBeenCalledWith('/production-lots/1/structure', expect.anything())
    expect(postMock).toHaveBeenCalledWith('/production-lots/1/positions/1/assign-internal', {
      orders: [{ machine_id: 5, quantity: 3 }],
    })
    expect(result.pendingAssignments.value).toEqual({})

    wrapper.unmount()
  })

  it('a new (negative-id) position PUTs the structure first, then assigns using the id the refetched lot reports at that index', async () => {
    const lot = makeLot({ positions: [makePosition({ id: 1, sequence: 1 })] })
    currentLotResponse = lot
    const { result, wrapper } = mountDraft(lot)
    await flushPromises()

    result.appendStep({ role: 'fabrication', fabrication_method_id: 1 })
    await flushPromises()

    const newPosition = result.draftPositions.value.find((p) => p.id < 0)
    expect(newPosition).toBeDefined()
    result.assignPosition(newPosition!.id, 'machine:5')
    await flushPromises()
    expect(result.isDirty.value).toBe(true)

    // The backend's response to the structure PUT: the new position now
    // has a real id (42) at index 1, the same index the draft submitted it
    // at, per ReplaceLotStructure's sequence = i + 1 rule.
    putMock.mockImplementationOnce((url: string) => {
      if (url === '/production-lots/1/structure') {
        currentLotResponse = makeLot({
          positions: [
            makePosition({ id: 1, sequence: 1 }),
            makePosition({
              id: 42,
              sequence: 2,
              quantity_remaining: 5,
              steps: [makeStep({ id: 42, position_id: 42, sequence: 1 })],
            }),
          ],
        })
      }
      return Promise.resolve({ data: [] })
    })

    const succeeded = await result.save(1)
    await flushPromises()

    expect(succeeded).toBe(true)
    expect(putMock).toHaveBeenCalledWith(
      '/production-lots/1/structure',
      expect.objectContaining({
        positions: [
          expect.objectContaining({ steps: [expect.objectContaining({ id: 1 })] }),
          expect.objectContaining({ steps: [expect.objectContaining({ id: null })] }),
        ],
      }),
    )
    expect(postMock).toHaveBeenCalledWith('/production-lots/1/positions/42/assign-internal', {
      orders: [{ machine_id: 5, quantity: 5 }],
    })
    expect(result.pendingAssignments.value).toEqual({})

    wrapper.unmount()
  })

  it('a staged reassign PUTs the order machine endpoint', async () => {
    const lot = makeLot({
      positions: [
        makePosition({
          id: 1,
          kind: 'internal',
          production_orders: [makeOrder({ id: 10 })],
        }),
      ],
    })
    currentLotResponse = lot
    const { result, wrapper } = mountDraft(lot)
    await flushPromises()

    result.reassignOrder(10, 'machine:5')
    await flushPromises()
    expect(result.pendingReassignments.value).toEqual({ 10: 'machine:5' })

    const succeeded = await result.save(1)
    await flushPromises()

    expect(succeeded).toBe(true)
    expect(putMock).toHaveBeenCalledWith('/production-orders/10/machine', { machine_id: 5 })
    expect(result.pendingReassignments.value).toEqual({})

    wrapper.unmount()
  })

  it('a rejected assign toasts, keeps the entry staged, and resolves false', async () => {
    const lot = makeLot({ positions: [makePosition({ id: 1 })] })
    currentLotResponse = lot
    const { result, wrapper } = mountDraft(lot)
    await flushPromises()

    result.assignPosition(1, 'machine:5')
    await flushPromises()

    postMock.mockRejectedValueOnce(new Error('boom'))
    const succeeded = await result.save(1)
    await flushPromises()

    expect(succeeded).toBe(false)
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'error',
        summary: expect.stringContaining('#1'),
      }),
    )
    expect(result.pendingAssignments.value).toEqual({ 1: 'machine:5' })

    wrapper.unmount()
  })

  it('a fully successful save resolves true and leaves both pending maps empty', async () => {
    const lot = makeLot({
      positions: [
        makePosition({ id: 1, kind: 'unassigned', sequence: 1 }),
        makePosition({
          id: 2,
          sequence: 2,
          kind: 'internal',
          steps: [makeStep({ id: 2, position_id: 2, sequence: 1 })],
          production_orders: [makeOrder({ id: 10 })],
        }),
      ],
    })
    currentLotResponse = lot
    const { result, wrapper } = mountDraft(lot)
    await flushPromises()

    result.assignPosition(1, 'machine:5')
    result.reassignOrder(10, 'pool:9')
    await flushPromises()

    const succeeded = await result.save(1)
    await flushPromises()

    expect(succeeded).toBe(true)
    expect(postMock).toHaveBeenCalledWith('/production-lots/1/positions/1/assign-internal', {
      orders: [{ machine_id: 5, quantity: 5 }],
    })
    expect(putMock).toHaveBeenCalledWith('/production-orders/10/machine', { machine_pool_id: 9 })
    expect(result.pendingAssignments.value).toEqual({})
    expect(result.pendingReassignments.value).toEqual({})

    wrapper.unmount()
  })
})
