import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { Permission } from '@/core/auth/permissions'

const postMock = vi
  .fn<(url: string, payload: unknown) => Promise<unknown>>()
  .mockResolvedValue({ data: {} })
const putMock = vi
  .fn<(url: string, payload: unknown) => Promise<unknown>>()
  .mockResolvedValue({ data: {} })
const getMock = vi.fn<(url: string) => Promise<unknown>>((url: string) => {
  if (url === '/inspection-methods/') {
    return Promise.resolve({
      data: { items: [INSPECTION_METHOD], total: 1, limit: 1000, skip: 0 },
    })
  }
  if (url === '/fabrication-methods/') {
    return Promise.resolve({
      data: { items: [FABRICATION_METHOD], total: 1, limit: 1000, skip: 0 },
    })
  }
  if (url === '/production-machines/') {
    return Promise.resolve({
      data: { items: [MACHINE, QA_MACHINE], total: 2, limit: 200, skip: 0 },
    })
  }
  if (url === '/production-machine-pools/') {
    return Promise.resolve({ data: { items: [POOL], total: 1, limit: 500, skip: 0 } })
  }
  if (url === '/orders/') {
    return Promise.resolve({ data: { items: [ORDER_FIXTURE], total: 1, limit: 200, skip: 0 } })
  }
  return Promise.resolve({ data: { items: [], total: 0, limit: 1000, skip: 0 } })
})

const MACHINE = {
  id: 1,
  public_id: '66666666-6666-6666-6666-666666666666',
  deleted: false,
  created: '2026-07-01',
  changed: null,
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
}

// The assign Select's QA-only path: an inspection position's Machines group
// is filtered down to is_qa_machine machines only (getCapableMachines).
const QA_MACHINE = {
  ...MACHINE,
  id: 2,
  public_id: '88888888-8888-8888-8888-888888888888',
  internal_name: 'QA Machine 1',
  fabrication_method_ids: [],
  is_qa_machine: true,
}

// Covers fabrication method 1 (MACHINE's): the grouped-select tests' pool
// option, alongside MACHINE itself.
const POOL = {
  id: 9,
  public_id: '77777777-7777-7777-7777-777777777777',
  deleted: false,
  created: '2026-07-01',
  changed: null,
  name: 'Mill Pool',
  machine_ids: [1],
  machines: [MACHINE],
  note: null,
  creator_id: 1,
  creator_full_name: 'Alice',
  changes: [],
}

const INSPECTION_METHOD = {
  id: 5,
  public_id: '55555555-5555-5555-5555-555555555555',
  created: '2026-01-01',
  changed: null,
  deleted: false,
  name: 'Visual Inspection',
  description: '',
  label_color: '#999999',
  label_font_color: '#000000',
  requires_evidence: false,
  archived: false,
  creator_id: 1,
  creator: null,
}

const FABRICATION_METHOD = {
  id: 1,
  public_id: '11111111-1111-1111-1111-111111111111',
  created: '2026-01-01',
  changed: null,
  deleted: false,
  name: 'Milling',
  description: '',
  label_color: '#999999',
  label_font_color: '#000000',
  requires_machine: true,
  required_external: false,
  default_supplier_id: null,
  archived: false,
  creator_id: 1,
  creator: null,
}

// One open purchase order, offered as the assign Select's Orders group.
const ORDER_FIXTURE = {
  id: 42,
  order_number: 'B-26-00042',
  supplier_name: 'ACME',
  status: 'ordered',
}

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    post: (url: string, payload: unknown) => postMock(url, payload),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import LotStepList from '../LotStepList.vue'
import { useProductionLotDetailStore } from '../../stores/productionLotDetailStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import {
  makeProductionOrderResponse,
  makeTestRouter,
  userWithPermissions,
} from '@/test-utils/factories'
import { useProductionQueueStore } from '../../../stores/productionQueueStore'
import type {
  LotPositionProductionOrderSummary,
  LotPositionResponse,
  LotStepResponse,
} from '../../../types/productionLotsResponse'

// The reassign Select requires write:production_orders and the assign Select
// requires it and/or write:orders. This is every mount's default so a test
// that is not about permissions sees an editable column.
const FULL_PERMISSIONS = [
  Permission.WRITE_LOTS,
  Permission.WRITE_PRODUCTION_ORDERS,
  Permission.WRITE_ORDERS,
]

function createTestPinia(permissions: string[] = FULL_PERMISSIONS) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  return pinia
}

const step: LotStepResponse = {
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
  role: 'fabrication' as const,
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

const position: LotPositionResponse = {
  id: 1,
  public_id: '22222222-2222-2222-2222-222222222222',
  created: '2026-07-01',
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
  steps: [step],
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

const inspectionStep: LotStepResponse = {
  id: 2,
  public_id: '22222222-2222-2222-2222-222222222222',
  created: '2026-07-01',
  note: null,
  estimated_setup_minutes: null,
  estimated_minutes_per_piece: null,
  time_budget_per_piece: null,
  sequence: 1,
  creator_id: 1,
  fabrication_method_id: null,
  role: 'inspection' as const,
  inspection_method_id: INSPECTION_METHOD.id,
  inspection_method_name: { enGB: INSPECTION_METHOD.name },
  inspection_method_requires_evidence: false,
  fabrication_method_name: { enGB: '' },
  fabrication_method_requires_machine: false,
  fabrication_method_required_external: false,
  fabrication_method_default_supplier_id: null,
  lot_id: 1,
  position_id: 2,
  source_process_id: null,
}

const inspectionPosition: LotPositionResponse = {
  ...position,
  id: 2,
  steps: [inspectionStep],
}

const assignedPosition: LotPositionResponse = {
  ...position,
  kind: 'internal',
  status: 'ordered_or_queued',
  production_orders: [
    {
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
    },
  ],
}

// A single queued order's machine_id/machine_pool_id vary per test; the
// step/quantity/status framing stays the same, only the target fields move.
function makeQueuedOrderPosition(
  orderOverrides: Partial<LotPositionProductionOrderSummary>,
): LotPositionResponse {
  return {
    ...position,
    kind: 'internal',
    status: 'ordered_or_queued',
    production_orders: [
      {
        id: 10,
        production_order_number: 'PO-0010',
        edit_version: 0,
        status: 'queued',
        priority: 'normal',
        quantity: 5,
        quantity_completed: 0,
        machine_id: null,
        machine_internal_name: '',
        machine_pool_id: null,
        machine_pool_name: '',
        conflicts: [],
        ...orderOverrides,
      },
    ],
  }
}

describe('LotStepList', () => {
  it('renders without errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(LotStepList, {
      pinia: createTestPinia(),
      attachTo: document.body,
      props: {
        lotId: 1,
        steps: [step],
        positions: [position],
        madeItemId: 1,
        madeItemPartNumber: 'PN-1',
        madeItemRevision: 'A',
        madeItemArticleName: 'Bracket',
        readonly: false,
      },
      global: {
        // The completion dialog's handbook drawer reads the route.
        plugins: [ConfirmationService, makeTestRouter()],
        stubs: { RouterLink: true },
      },
    })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    wrapper.unmount()
  })

  // Two grouped fabrication steps in position 1, the QA singleton in
  // position 2: the shape a require_qa lot is born with.
  const secondStep = {
    ...step,
    id: 3,
    sequence: 2,
    public_id: '33333333-3333-3333-3333-333333333333',
    fabrication_method_name: { enGB: 'Drilling' },
  }
  const groupedPosition = { ...position, steps: [step, secondStep] }
  const qaPosition = { ...inspectionPosition, sequence: 2 }

  function mountGrouped() {
    return mountWithApp(LotStepList, {
      pinia: createTestPinia(),
      attachTo: document.body,
      props: {
        lotId: 1,
        steps: [step, secondStep, { ...inspectionStep, sequence: 3 }],
        positions: [groupedPosition, qaPosition],
        madeItemId: 1,
        madeItemPartNumber: 'PN-1',
        madeItemRevision: 'A',
        madeItemArticleName: 'Bracket',
        readonly: false,
      },
      global: {
        plugins: [ConfirmationService],
        stubs: { RouterLink: true },
      },
    })
  }

  it('renders one position cell per position, spanned across its steps', async () => {
    const wrapper = mountGrouped()
    await flushPromises()
    await flushPromises()

    // Three step rows, but only two position cells: the grouped position
    // renders its cell once with a rowspan.
    const positionCells = wrapper.findAll('.position-cell')
    expect(positionCells).toHaveLength(2)
    expect(positionCells[0]!.text()).toContain('#1')
    expect(positionCells[0]!.text()).toContain('2 steps in one position')
    expect(positionCells[1]!.text()).toContain('#2')
    expect(positionCells[1]!.find('.position-cell-count').exists()).toBe(false)

    // One drag handle per position, not per step.
    expect(wrapper.findAll('[data-testid="step-reorder-handle"]')).toHaveLength(2)

    wrapper.unmount()
  })

  it('hovering any step of a position highlights the whole position', async () => {
    const wrapper = mountGrouped()
    await flushPromises()
    await flushPromises()

    const dataRows = wrapper.findAll('tr[data-p-index]')
    expect(dataRows).toHaveLength(3)

    // Hover the SECOND step of the grouped position: the row that owns
    // none of the spanned cells, which is where the half-highlight showed.
    await dataRows[1]!.find('td').trigger('mouseover')

    expect(dataRows[0]!.classes()).toContain('position-row-hovered')
    expect(dataRows[1]!.classes()).toContain('position-row-hovered')
    // The QA position is a different group and stays untinted.
    expect(dataRows[2]!.classes()).not.toContain('position-row-hovered')

    await wrapper.find('.step-table').trigger('mouseleave')
    expect(wrapper.findAll('.position-row-hovered')).toHaveLength(0)

    wrapper.unmount()
  })

  it('dragging a position moves its whole block of steps', async () => {
    const wrapper = mountGrouped()
    await flushPromises()
    await flushPromises()

    const detailStore = useProductionLotDetailStore()
    const reorderSteps = vi.fn<(lotId: number, ids: number[]) => Promise<void>>(() =>
      Promise.resolve(),
    )
    detailStore.reorderSteps = reorderSteps

    // Drag the QA position (row 2) above the grouped position (row 0).
    await wrapper
      .findComponent({ name: 'DataTable' })
      .vm.$emit('rowReorder', { value: [], dragIndex: 2, dropIndex: 0 })
    await flushPromises()

    // The two grouped steps stay together and keep their internal order.
    expect(reorderSteps).toHaveBeenCalledWith(1, [2, 1, 3])

    wrapper.unmount()
  })

  it('disables deleting a step whose position is already assigned', async () => {
    const wrapper = mountWithApp(LotStepList, {
      pinia: createTestPinia(),
      attachTo: document.body,
      props: {
        lotId: 1,
        steps: [step],
        positions: [assignedPosition],
        madeItemId: 1,
        madeItemPartNumber: 'PN-1',
        madeItemRevision: 'A',
        madeItemArticleName: 'Bracket',
        readonly: false,
      },
      global: {
        plugins: [ConfirmationService],
        stubs: { RouterLink: true },
      },
    })

    await flushPromises()
    await flushPromises()

    const button = wrapper.get('button[aria-label="Remove Step"]').element as HTMLButtonElement
    expect(button.disabled).toBe(true)

    wrapper.unmount()
  })

  it('leaves delete enabled for an unassigned position', async () => {
    const wrapper = mountWithApp(LotStepList, {
      pinia: createTestPinia(),
      attachTo: document.body,
      props: {
        lotId: 1,
        steps: [step],
        positions: [position],
        madeItemId: 1,
        madeItemPartNumber: 'PN-1',
        madeItemRevision: 'A',
        madeItemArticleName: 'Bracket',
        readonly: false,
      },
      global: {
        plugins: [ConfirmationService],
        stubs: { RouterLink: true },
      },
    })

    await flushPromises()
    await flushPromises()

    const button = wrapper.get('button[aria-label="Remove Step"]').element as HTMLButtonElement
    expect(button.disabled).toBe(false)

    wrapper.unmount()
  })

  it('renders an inspection method Select for an inspection step, not a fabrication method Select', async () => {
    const wrapper = mountWithApp(LotStepList, {
      pinia: createTestPinia(),
      attachTo: document.body,
      props: {
        lotId: 1,
        steps: [inspectionStep],
        positions: [inspectionPosition],
        madeItemId: 1,
        madeItemPartNumber: 'PN-1',
        madeItemRevision: 'A',
        madeItemArticleName: 'Bracket',
        readonly: false,
      },
      global: {
        plugins: [ConfirmationService],
        stubs: { RouterLink: true },
      },
    })

    await flushPromises()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'Select' })
    const methodSelect = selects.find((s) =>
      (s.props('options') as { id: number }[] | undefined)?.some(
        (o) => o.id === inspectionStep.inspection_method_id,
      ),
    )
    expect(methodSelect).toBeDefined()
    expect(methodSelect!.props('modelValue')).toBe(inspectionStep.inspection_method_id)

    wrapper.unmount()
  })

  it('the "Add Inspection" split-button item appends a new position at the end of the lot, holding just that step', async () => {
    postMock.mockClear()

    const wrapper = mountWithApp(LotStepList, {
      pinia: createTestPinia(),
      attachTo: document.body,
      props: {
        lotId: 1,
        steps: [step],
        positions: [position],
        madeItemId: 1,
        madeItemPartNumber: 'PN-1',
        madeItemRevision: 'A',
        madeItemArticleName: 'Bracket',
        readonly: false,
      },
      global: {
        plugins: [ConfirmationService],
        stubs: { RouterLink: true },
      },
    })

    await flushPromises()
    await flushPromises()

    const addInspectionButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Add Inspection')
    expect(addInspectionButton).toBeDefined()

    await addInspectionButton!.trigger('click')
    await flushPromises()

    // Appending a position, not adding into the last unassigned one: an
    // inspection step must be the sole occupant of its position, and
    // AddLotStep cannot create one.
    expect(postMock).toHaveBeenCalledWith('/production-lots/1/positions', {
      steps: [
        expect.objectContaining({
          role: 'inspection',
          inspection_method_id: INSPECTION_METHOD.id,
        }),
      ],
    })

    wrapper.unmount()
  })

  it('the "Add" button appends a fabrication step as its own position too', async () => {
    postMock.mockClear()

    const wrapper = mountWithApp(LotStepList, {
      pinia: createTestPinia(),
      attachTo: document.body,
      props: {
        lotId: 1,
        steps: [step],
        positions: [position],
        madeItemId: 1,
        madeItemPartNumber: 'PN-1',
        madeItemRevision: 'A',
        madeItemArticleName: 'Bracket',
        readonly: false,
      },
      global: {
        plugins: [ConfirmationService],
        stubs: { RouterLink: true },
      },
    })

    await flushPromises()
    await flushPromises()

    const addButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Add Step')
    await addButton!.trigger('click')
    await flushPromises()

    expect(postMock).toHaveBeenCalledWith('/production-lots/1/positions', {
      steps: [expect.objectContaining({ role: 'fabrication', fabrication_method_id: 1 })],
    })

    wrapper.unmount()
  })

  it('shows Complete on an inspection position disabled with the missing permission without write:inspections', async () => {
    const pos: LotPositionResponse = {
      ...inspectionPosition,
      kind: 'internal',
      status: 'ordered_or_queued',
      production_orders: assignedPosition.production_orders,
    }
    const pinia = createTestPinia([Permission.WRITE_LOTS, Permission.WRITE_PRODUCTION_ORDERS])
    useProductionQueueStore().orders = [
      makeProductionOrderResponse({ id: 10, status: 'in_progress', actions: ['record_completion'] }),
    ]
    const wrapper = mountWithApp(LotStepList, {
      pinia,
      attachTo: document.body,
      props: {
        lotId: 1,
        steps: pos.steps ?? [],
        positions: [pos],
        madeItemId: 1,
        madeItemPartNumber: 'PN-1',
        madeItemRevision: 'A',
        madeItemArticleName: 'Bracket',
        readonly: false,
      },
      global: { plugins: [ConfirmationService], stubs: { RouterLink: true } },
    })
    await flushPromises()

    const complete = wrapper.get('[data-testid="lot-step-complete"]')
    expect(complete.attributes('disabled')).toBeDefined()
    const span = complete.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Record QA Inspections.')

    wrapper.unmount()
  })

  describe('machine column: pool-or-machine target select', () => {
    function mountWithPosition(pos: LotPositionResponse) {
      return mountWithApp(LotStepList, {
        pinia: createTestPinia(),
        attachTo: document.body,
        props: {
          lotId: 1,
          steps: pos.steps ?? [],
          positions: [pos],
          madeItemId: 1,
          madeItemPartNumber: 'PN-1',
          madeItemRevision: 'A',
          madeItemArticleName: 'Bracket',
          readonly: false,
        },
        global: {
          plugins: [ConfirmationService],
          stubs: { RouterLink: true },
        },
      })
    }

    function targetSelect(wrapper: ReturnType<typeof mountWithPosition>) {
      return wrapper.get('.machine-cell').findComponent({ name: 'Select' })
    }

    it('shows the target select disabled with the missing permission without write:production_orders', async () => {
      const wrapper = mountWithApp(LotStepList, {
        pinia: createTestPinia([Permission.WRITE_LOTS]),
        attachTo: document.body,
        props: {
          lotId: 1,
          steps: makeQueuedOrderPosition({}).steps ?? [],
          positions: [makeQueuedOrderPosition({})],
          madeItemId: 1,
          madeItemPartNumber: 'PN-1',
          madeItemRevision: 'A',
          madeItemArticleName: 'Bracket',
          readonly: false,
        },
        global: {
          plugins: [ConfirmationService],
          stubs: { RouterLink: true },
        },
      })
      await flushPromises()
      await flushPromises()

      const cell = wrapper.get('[data-testid="lot-step-machine-select"]')
      expect(cell.findComponent({ name: 'Select' }).props('disabled')).toBe(true)
      expect((cell.element as HTMLElement & { $_ptooltipValue?: string }).$_ptooltipValue).toBe(
        'This needs the permission Write Production Orders.',
      )

      wrapper.unmount()
    })

    it('offers covering pools and capable machines as grouped options', async () => {
      const wrapper = mountWithPosition(makeQueuedOrderPosition({}))
      await flushPromises()
      await flushPromises()

      const options = targetSelect(wrapper).props('options') as {
        key: string
        items: { key: string; label: string }[]
      }[]
      const poolGroup = options.find((g) => g.key === 'pools')
      const machineGroup = options.find((g) => g.key === 'machines')
      expect(poolGroup?.items).toEqual([{ key: 'pool:9', label: 'Mill Pool' }])
      expect(machineGroup?.items).toEqual([{ key: 'machine:1', label: 'Machine 1' }])

      wrapper.unmount()
    })

    it('displays the machine when machine_id is set, machine-only', async () => {
      const wrapper = mountWithPosition(makeQueuedOrderPosition({ machine_id: 1 }))
      await flushPromises()
      await flushPromises()

      expect(targetSelect(wrapper).props('modelValue')).toBe('machine:1')
      expect(wrapper.find('.machine-pool-note').exists()).toBe(false)

      wrapper.unmount()
    })

    it('displays the pool when only machine_pool_id is set, pool-only (unresolved)', async () => {
      const wrapper = mountWithPosition(
        makeQueuedOrderPosition({ machine_pool_id: 9, machine_pool_name: 'Mill Pool' }),
      )
      await flushPromises()
      await flushPromises()

      expect(targetSelect(wrapper).props('modelValue')).toBe('pool:9')
      // Resolved-from-pool provenance note only applies once a machine has
      // actually been picked; nothing extra to say while still unresolved.
      expect(wrapper.find('.machine-pool-note').exists()).toBe(false)

      wrapper.unmount()
    })

    it('displays the machine plus a pool-provenance note once resolved (both set)', async () => {
      const wrapper = mountWithPosition(
        makeQueuedOrderPosition({
          machine_id: 1,
          machine_pool_id: 9,
          machine_pool_name: 'Mill Pool',
        }),
      )
      await flushPromises()
      await flushPromises()

      expect(targetSelect(wrapper).props('modelValue')).toBe('machine:1')
      expect(wrapper.find('.machine-pool-note').text()).toContain('Mill Pool')

      wrapper.unmount()
    })

    it('reassigns with a plain machine id when a machine option is picked', async () => {
      const wrapper = mountWithPosition(makeQueuedOrderPosition({}))
      await flushPromises()
      await flushPromises()
      putMock.mockClear()

      await targetSelect(wrapper).vm.$emit('update:modelValue', 'machine:1')
      await flushPromises()

      expect(putMock).toHaveBeenCalledWith('/production-orders/10/machine', { machine_id: 1 })

      wrapper.unmount()
    })

    it('reassigns with machine_pool_id when a pool option is picked', async () => {
      const wrapper = mountWithPosition(makeQueuedOrderPosition({}))
      await flushPromises()
      await flushPromises()
      putMock.mockClear()

      await targetSelect(wrapper).vm.$emit('update:modelValue', 'pool:9')
      await flushPromises()

      expect(putMock).toHaveBeenCalledWith('/production-orders/10/machine', {
        machine_pool_id: 9,
      })

      wrapper.unmount()
    })
  })

  describe('machine/order column: assigning an unassigned position', () => {
    // Manual-only: every step's fabrication method skips a machine, so the
    // assign Select offers "Queue without machine" instead of Pools/Machines.
    const manualStep: LotStepResponse = {
      ...step,
      id: 4,
      position_id: 3,
      fabrication_method_id: 3,
      fabrication_method_name: { enGB: 'Deburring' },
      fabrication_method_requires_machine: false,
    }
    const manualPosition: LotPositionResponse = { ...position, id: 3, steps: [manualStep] }

    // Draft-only (never saved to the backend); assignableFor requires id > 0.
    const draftStep: LotStepResponse = { ...step, position_id: -1 }
    const draftPosition: LotPositionResponse = { ...position, id: -1, steps: [draftStep] }

    const externalPosition: LotPositionResponse = {
      ...position,
      kind: 'external',
      order_id: 42,
      order_number: 'B-26-00042',
      supplier_name: 'ACME',
      order_item_id: 1,
      order_item_status: 'ordered',
      order_item_closed_short: false,
    }

    function mountAssign(
      pos: LotPositionResponse,
      options: {
        permissions?: string[]
        readonly?: boolean
        staged?: boolean
        pendingAssignments?: Record<number, string>
        pendingReassignments?: Record<number, string | null>
      } = {},
    ) {
      return mountWithApp(LotStepList, {
        pinia: createTestPinia(options.permissions ?? FULL_PERMISSIONS),
        attachTo: document.body,
        props: {
          lotId: 1,
          steps: pos.steps ?? [],
          positions: [pos],
          madeItemId: 1,
          madeItemPartNumber: 'PN-1',
          madeItemRevision: 'A',
          madeItemArticleName: 'Bracket',
          readonly: options.readonly ?? false,
          staged: options.staged ?? false,
          pendingAssignments: options.pendingAssignments,
          pendingReassignments: options.pendingReassignments,
        },
        global: {
          plugins: [ConfirmationService],
          stubs: { RouterLink: true },
        },
      })
    }

    function assignSelect(wrapper: ReturnType<typeof mountAssign>) {
      return wrapper.get('.machine-cell--assign').findComponent({ name: 'Select' })
    }

    it('renders the assign Select with grouped options for an unassigned machine-requiring position', async () => {
      const wrapper = mountAssign(position)
      await flushPromises()
      await flushPromises()

      const options = assignSelect(wrapper).props('options') as { key: string }[]
      expect(options.map((g) => g.key)).toEqual(['pools', 'machines', 'orders', 'create'])

      wrapper.unmount()
    })

    it('offers only the QA machine for a QA unassigned position', async () => {
      const wrapper = mountAssign(inspectionPosition)
      await flushPromises()
      await flushPromises()

      const options = assignSelect(wrapper).props('options') as {
        key: string
        items: { key: string; label: string }[]
      }[]
      expect(options.map((g) => g.key)).toEqual(['machines'])
      expect(options[0]!.items).toEqual([{ key: 'machine:2', label: 'QA Machine 1' }])

      wrapper.unmount()
    })

    it('offers "Queue without machine" and no machines/pools for a manual-only position', async () => {
      const wrapper = mountAssign(manualPosition)
      await flushPromises()
      await flushPromises()

      const options = assignSelect(wrapper).props('options') as {
        key: string
        items: { key: string; label: string }[]
      }[]
      expect(options.map((g) => g.key)).toEqual(['manual', 'orders', 'create'])
      expect(options.find((g) => g.key === 'manual')!.items).toEqual([
        { key: 'manual', label: 'Queue without machine' },
      ])

      wrapper.unmount()
    })

    it('picking a machine posts assign-internal and refetches queue orders', async () => {
      const wrapper = mountAssign(position)
      await flushPromises()
      await flushPromises()
      postMock.mockClear()
      getMock.mockClear()

      await assignSelect(wrapper).vm.$emit('update:modelValue', 'machine:1')
      await flushPromises()
      await flushPromises()

      expect(postMock).toHaveBeenCalledWith('/production-lots/1/positions/1/assign-internal', {
        orders: [{ machine_id: 1, quantity: 5 }],
      })
      expect(getMock.mock.calls.some((call) => call[0] === '/production-orders/')).toBe(true)

      wrapper.unmount()
    })

    it('picking a pool posts assign-internal with machine_pool_id', async () => {
      const wrapper = mountAssign(position)
      await flushPromises()
      await flushPromises()
      postMock.mockClear()

      await assignSelect(wrapper).vm.$emit('update:modelValue', 'pool:9')
      await flushPromises()
      await flushPromises()

      expect(postMock).toHaveBeenCalledWith('/production-lots/1/positions/1/assign-internal', {
        orders: [{ machine_pool_id: 9, quantity: 5 }],
      })

      wrapper.unmount()
    })

    it('picking "Queue without machine" posts assign-internal with a null machine_id', async () => {
      const wrapper = mountAssign(manualPosition)
      await flushPromises()
      await flushPromises()
      postMock.mockClear()

      await assignSelect(wrapper).vm.$emit('update:modelValue', 'manual')
      await flushPromises()
      await flushPromises()

      expect(postMock).toHaveBeenCalledWith('/production-lots/1/positions/3/assign-internal', {
        orders: [{ machine_id: null, quantity: 5 }],
      })

      wrapper.unmount()
    })

    it('picking an order posts the external assign with the full remaining quantity', async () => {
      const wrapper = mountAssign(position)
      await flushPromises()
      await flushPromises()
      postMock.mockClear()

      await assignSelect(wrapper).vm.$emit('update:modelValue', `order:${ORDER_FIXTURE.id}`)
      await flushPromises()
      await flushPromises()

      expect(postMock).toHaveBeenCalledWith('/production-lots/1/positions/1/assign', {
        order_id: ORDER_FIXTURE.id,
        unit: 'PCS',
        items_per_unit: 1,
        price: null,
        expected_delivery_date: null,
        expected_pickup_date: null,
        quantity: 5,
      })

      wrapper.unmount()
    })

    it('order:new opens OrderCreateForm and assigns externally once it emits created', async () => {
      const wrapper = mountAssign(position)
      await flushPromises()
      await flushPromises()
      postMock.mockClear()

      await assignSelect(wrapper).vm.$emit('update:modelValue', 'order:new')
      await flushPromises()

      const createForm = wrapper.findComponent({ name: 'OrderCreateForm' })
      expect(createForm.exists()).toBe(true)
      expect(createForm.props('visible')).toBe(true)
      expect(postMock).not.toHaveBeenCalled()

      createForm.vm.$emit('created', { id: 77, order_number: 'B-26-00077', supplier_name: 'Globex' })
      await flushPromises()
      await flushPromises()

      expect(postMock).toHaveBeenCalledWith(
        '/production-lots/1/positions/1/assign',
        expect.objectContaining({ order_id: 77, quantity: 5 }),
      )

      wrapper.unmount()
    })

    it('renders the assign Select disabled with the missing permission without write:production_orders or write:orders', async () => {
      const wrapper = mountAssign(position, { permissions: [Permission.WRITE_LOTS] })
      await flushPromises()
      await flushPromises()

      const cell = wrapper.get('.machine-cell--assign')
      expect(cell.findComponent({ name: 'Select' }).props('disabled')).toBe(true)
      expect((cell.element as HTMLElement & { $_ptooltipValue?: string }).$_ptooltipValue).toBe(
        'This needs the permission Write Production Orders.',
      )

      wrapper.unmount()
    })

    it('omits the orders/create groups when only write:orders is missing', async () => {
      const wrapper = mountAssign(position, {
        permissions: [Permission.WRITE_LOTS, Permission.WRITE_PRODUCTION_ORDERS],
      })
      await flushPromises()
      await flushPromises()

      const options = assignSelect(wrapper).props('options') as { key: string }[]
      expect(options.map((g) => g.key)).toEqual(['pools', 'machines'])

      wrapper.unmount()
    })

    it('renders no Select for a draft (unsaved) position', async () => {
      const wrapper = mountAssign(draftPosition)
      await flushPromises()
      await flushPromises()

      expect(wrapper.find('.machine-cell--assign').exists()).toBe(false)
      expect(wrapper.find('.machine-cell').exists()).toBe(false)

      wrapper.unmount()
    })

    it('an external position renders the order link and opens OrderDetailDialog on click', async () => {
      const wrapper = mountAssign(externalPosition)
      await flushPromises()
      await flushPromises()

      const link = wrapper.get('.machine-order-link')
      expect(link.text()).toBe('B-26-00042 · ACME')

      await link.trigger('click')
      await flushPromises()

      const dialog = wrapper.findComponent({ name: 'OrderDetailDialog' })
      expect(dialog.props('visible')).toBe(true)
      expect(dialog.props('orderId')).toBe(42)

      wrapper.unmount()
    })

    it('a rejected assign shows no uncaught error and re-enables the Select', async () => {
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const wrapper = mountAssign(position)
      await flushPromises()
      await flushPromises()

      postMock.mockRejectedValueOnce(new Error('boom'))

      await assignSelect(wrapper).vm.$emit('update:modelValue', 'machine:1')
      await flushPromises()
      await flushPromises()

      expect(errorSpy).not.toHaveBeenCalled()
      expect(assignSelect(wrapper).props('disabled')).toBe(false)

      errorSpy.mockRestore()
      wrapper.unmount()
    })
  })

  describe('machine/order column: staged mode', () => {
    // Draft-only (never saved to the backend): staged mode drops the id > 0
    // requirement assignableFor otherwise enforces (Save maps the pick onto
    // the real id the saved structure hands back for this slot).
    const draftStep: LotStepResponse = { ...step, position_id: -1 }
    const draftPosition: LotPositionResponse = { ...position, id: -1, steps: [draftStep] }

    function mountStaged(
      pos: LotPositionResponse,
      options: {
        pendingAssignments?: Record<number, string>
        pendingReassignments?: Record<number, string | null>
      } = {},
    ) {
      return mountWithApp(LotStepList, {
        pinia: createTestPinia(),
        attachTo: document.body,
        props: {
          lotId: 1,
          steps: pos.steps ?? [],
          positions: [pos],
          madeItemId: 1,
          madeItemPartNumber: 'PN-1',
          madeItemRevision: 'A',
          madeItemArticleName: 'Bracket',
          readonly: false,
          staged: true,
          pendingAssignments: options.pendingAssignments,
          pendingReassignments: options.pendingReassignments,
        },
        global: {
          plugins: [ConfirmationService],
          stubs: { RouterLink: true },
        },
      })
    }

    function assignSelect(wrapper: ReturnType<typeof mountStaged>) {
      return wrapper.get('.machine-cell--assign').findComponent({ name: 'Select' })
    }

    it('picking an assign target emits assignPosition instead of posting', async () => {
      const wrapper = mountStaged(position)
      await flushPromises()
      await flushPromises()
      postMock.mockClear()

      await assignSelect(wrapper).vm.$emit('update:modelValue', 'machine:1')
      await flushPromises()

      expect(wrapper.emitted('assignPosition')).toEqual([[1, 'machine:1']])
      expect(postMock).not.toHaveBeenCalled()

      wrapper.unmount()
    })

    it("shows the pending assignment as the Select's modelValue, with clear enabled", async () => {
      const wrapper = mountStaged(position, { pendingAssignments: { 1: 'machine:1' } })
      await flushPromises()
      await flushPromises()

      expect(assignSelect(wrapper).props('modelValue')).toBe('machine:1')
      expect(assignSelect(wrapper).props('showClear')).toBe(true)

      wrapper.unmount()
    })

    it('clearing a pending assignment emits clearAssignment', async () => {
      const wrapper = mountStaged(position, { pendingAssignments: { 1: 'machine:1' } })
      await flushPromises()
      await flushPromises()

      await assignSelect(wrapper).vm.$emit('update:modelValue', null)
      await flushPromises()

      expect(wrapper.emitted('clearAssignment')).toEqual([[1]])

      wrapper.unmount()
    })

    it('a draft (negative-id) position is assignable in staged mode', async () => {
      const wrapper = mountStaged(draftPosition)
      await flushPromises()
      await flushPromises()

      expect(wrapper.find('.machine-cell--assign').exists()).toBe(true)

      wrapper.unmount()
    })

    it('a reassign pick emits reassignOrder with no PUT, and clearReassignment when picking the current target back', async () => {
      const wrapper = mountStaged(makeQueuedOrderPosition({ machine_id: 1 }))
      await flushPromises()
      await flushPromises()
      putMock.mockClear()

      const select = wrapper.get('.machine-cell').findComponent({ name: 'Select' })

      await select.vm.$emit('update:modelValue', 'pool:9')
      await flushPromises()

      expect(wrapper.emitted('reassignOrder')).toEqual([[10, 'pool:9']])
      expect(putMock).not.toHaveBeenCalled()

      await select.vm.$emit('update:modelValue', 'machine:1')
      await flushPromises()

      expect(wrapper.emitted('clearReassignment')).toEqual([[10]])
      expect(putMock).not.toHaveBeenCalled()

      wrapper.unmount()
    })

    it("order:new + created emits assignPosition with the new order's key", async () => {
      const wrapper = mountStaged(position)
      await flushPromises()
      await flushPromises()
      postMock.mockClear()

      await assignSelect(wrapper).vm.$emit('update:modelValue', 'order:new')
      await flushPromises()

      const createForm = wrapper.findComponent({ name: 'OrderCreateForm' })
      expect(createForm.props('visible')).toBe(true)

      createForm.vm.$emit('created', { id: 42, order_number: 'B-26-00042', supplier_name: 'ACME' })
      await flushPromises()

      expect(wrapper.emitted('assignPosition')).toEqual([[1, 'order:42']])
      expect(postMock).not.toHaveBeenCalled()

      wrapper.unmount()
    })
  })
})
