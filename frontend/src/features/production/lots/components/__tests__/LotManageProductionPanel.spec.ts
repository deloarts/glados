import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useProductionLotDetailStore } from '../../stores/productionLotDetailStore'

import type { ProductionMachineResponse } from '@/features/production-machines'
import type { MachinePoolResponse } from '@/features/production-machines'

const { machinesFixture, poolsFixture } = vi.hoisted(() => {
  const machinesFixture: ProductionMachineResponse[] = [
    {
      id: 1,
      public_id: '11111111-1111-1111-1111-111111111111',
      archived: false,
      created: '2026-07-01',
      changed: null,
      changed_by_id: null,
      changed_by_full_name: '',
      internal_name: 'Mill A',
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
    },
    {
      id: 2,
      public_id: '22222222-2222-2222-2222-222222222222',
      archived: false,
      created: '2026-07-01',
      changed: null,
      changed_by_id: null,
      changed_by_full_name: '',
      internal_name: 'Mill B',
      vendor: 'Acme',
      model: 'M200',
      fabrication_method_ids: [2],
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
    },
  ]
  // Covers fabrication method 1 only (Mill A's): the auto-flow tests'
  // "there is exactly one covering pool" fixture. Left out of
  // currentPools() by default so every other test's positions (which
  // default to method 1 too) still see "no covering pool", same as before
  // pools existed at all. Opted into explicitly per test.
  const poolsFixture: MachinePoolResponse[] = [
    {
      id: 9,
      public_id: '99999999-9999-9999-9999-999999999999',
      archived: false,
      created: '2026-07-01',
      changed: null,
      changed_by_id: null,
      changed_by_full_name: '',
      name: 'Mill Pool',
      machine_ids: [1],
      machines: [machinesFixture[0]!],
      note: null,
      creator_id: 1,
      creator_full_name: 'Alice',
      changes: [],
    },
  ]
  return { machinesFixture, poolsFixture }
})

// Toggled per test: most tests want "no pool covers anything" (matching
// behaviour from before pools existed at all), the auto-flow tests opt into
// poolsFixture explicitly.
let currentPools: MachinePoolResponse[] = []

// Toggled per test, same idiom as currentPools above. Most tests use the
// plain two-machine fixture, the archived-picker test below swaps in one
// that includes an archived machine.
let currentMachines: ProductionMachineResponse[] = machinesFixture

// Any post-mutation refetch (GET /production-lots/{id}) just resolves to an
// empty-positions lot, these tests assert on the mutation call itself, not
// on the store's state after the follow-up refetch.
const getMock = vi.fn<(url: string) => Promise<unknown>>().mockImplementation((url: string) => {
  if (url.startsWith('/production-lots/')) {
    return Promise.resolve({
      data: {
        id: 1,
        created: '2026-07-01',
        changed: null,
        lot_number: 'LOT-1',
        quantity: 10,
        quantity_completed: 0,
        status: 'draft',
        priority: 'normal',
        note: null,
        creator_id: 1,
        creator: null,
        made_item_id: 1,
        made_item_part_number: 'PN-1',
        source_bought_item_id: null,
        source_item_id: null,
        source_made_item_id: null,
        source_label: '',
        source_sublabel: '',
        demand_status: '',
        made_item_article_name: 'Bracket',
        made_item_revision: 'A',
        made_item_material: '1.0037',
        project_id: 42,
        project_number: 'P-001',
        project_customer: 'Acme',
        input_demand_id: null,
        positions: [],
        steps: [],
      },
    })
  }
  if (url === '/production-machine-pools/') {
    return Promise.resolve({
      data: { items: currentPools, total: currentPools.length, limit: 500, skip: 0 },
    })
  }
  return Promise.resolve({
    data: { items: currentMachines, total: currentMachines.length, limit: 200, skip: 0 },
  })
})

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import LotManageProductionPanel from '../LotManageProductionPanel.vue'

import type {
  FabricationLotStep,
  LotPositionResponse,
  LotStepResponse,
} from '../../../types/productionLotsResponse'
import { makeLot, positionActions } from '../../__tests__/fixtures'

function makeStep(overrides: Partial<FabricationLotStep> = {}): LotStepResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-07-01',
    note: null,
    estimated_setup_minutes: null,
    estimated_minutes_per_piece: null,
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
    ...overrides,
  }
}

function makePosition(overrides: Partial<LotPositionResponse> = {}): LotPositionResponse {
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
  return { ...position, actions: overrides.actions ?? positionActions(position) }
}

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(LotManageProductionPanel, {
    pinia,
    props: { lotId: 1 },
    global: {
      stubs: { RouterLink: true },
    },
  })
  return { wrapper, detailStore: useProductionLotDetailStore() }
}

describe('LotManageProductionPanel', () => {
  beforeEach(() => {
    currentPools = []
    currentMachines = machinesFixture
  })

  it('renders every unassigned position on the loaded lot', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([makePosition({ id: 1 }), makePosition({ id: 2, sequence: 2 })])
    await flushPromises()

    const rows = wrapper.findAll('.row-card')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.text()).toContain('Milling')
  })

  it('assigns the full position quantity to the selected machine on click', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([makePosition({ id: 1, quantity: 7, quantity_remaining: 7 })])
    detailStore.assignInternal = vi
      .fn<typeof detailStore.assignInternal>()
      .mockResolvedValue(undefined)
    await flushPromises()

    const machineSelect = wrapper.findComponent({ name: 'Select' })
    await machineSelect.vm.$emit('update:modelValue', 1)
    await flushPromises()

    await wrapper.get('.row-header').trigger('click')
    await flushPromises()

    expect(detailStore.assignInternal).toHaveBeenCalledWith(1, 1, {
      orders: [{ machine_id: 1, quantity: 7 }],
    })
  })

  // Referencing an already-archived machine is allowed. Selecting one as
  // the assignment target shows the Archived tag on the selection and the
  // warning line below the control (see useArchivableOptions.ts).
  it('shows the Archived tag and warning line when an archived machine is picked as the target', async () => {
    currentMachines = [
      ...machinesFixture,
      { ...machinesFixture[0]!, id: 3, internal_name: 'Retired Mill', archived: true },
    ]
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([makePosition({ id: 1 })])
    await flushPromises()

    const machineSelect = wrapper.findComponent({ name: 'Select' })
    await machineSelect.vm.$emit('update:modelValue', 3)
    await flushPromises()

    expect(wrapper.text()).toContain(i18n.global.t('common.archivedTag'))
    expect(wrapper.text()).toContain(i18n.global.t('common.archivedSelectionWarning'))
  })

  it('disables and flags a position the selected machine cannot fulfil', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([
      makePosition({ id: 1, steps: [makeStep({ fabrication_method_id: 2 })] }),
    ])
    await flushPromises()

    const machineSelect = wrapper.findComponent({ name: 'Select' })
    await machineSelect.vm.$emit('update:modelValue', 1) // Mill A only covers method 1
    await flushPromises()

    const row = wrapper.get('.row-card')
    expect(row.classes()).toContain('row-card--warning')
    expect(row.find('.warning-badge').exists()).toBe(true)
    expect(row.get('.row-header').classes()).toContain('row-header--disabled')
  })

  it('flags but does not disable a position with a typically-outsourced step', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([
      makePosition({
        id: 1,
        steps: [makeStep({ fabrication_method_id: 1, fabrication_method_required_external: true })],
      }),
    ])
    detailStore.assignInternal = vi
      .fn<typeof detailStore.assignInternal>()
      .mockResolvedValue(undefined)
    await flushPromises()

    const machineSelect = wrapper.findComponent({ name: 'Select' })
    await machineSelect.vm.$emit('update:modelValue', 1)
    await flushPromises()

    const row = wrapper.get('.row-card')
    expect(row.classes()).not.toContain('row-card--warning')
    expect(row.classes()).toContain('row-card--external-note')
    expect(row.get('.row-header').classes()).not.toContain('row-header--disabled')

    await row.get('.row-header').trigger('click')
    await flushPromises()

    expect(detailStore.assignInternal).toHaveBeenCalled()
  })

  it('does not assign when clicking a position before a machine is selected', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([makePosition({ id: 1 })])
    detailStore.assignInternal = vi
      .fn<typeof detailStore.assignInternal>()
      .mockResolvedValue(undefined)
    await flushPromises()

    await wrapper.get('.row-header').trigger('click')
    await flushPromises()

    expect(detailStore.assignInternal).not.toHaveBeenCalled()
  })

  it('auto-flow: shows the resolved-pool tag and assigns to it on click when no target is picked', async () => {
    currentPools = poolsFixture
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([makePosition({ id: 1, quantity: 7, quantity_remaining: 7 })])
    detailStore.assignInternal = vi
      .fn<typeof detailStore.assignInternal>()
      .mockResolvedValue(undefined)
    await flushPromises()

    const row = wrapper.get('.row-card')
    expect(row.text()).toContain('Mill Pool')
    expect(row.classes()).not.toContain('row-card--warning')
    expect(row.get('.row-header').classes()).not.toContain('row-header--disabled')

    await row.get('.row-header').trigger('click')
    await flushPromises()

    expect(detailStore.assignInternal).toHaveBeenCalledWith(1, 1, {
      orders: [{ machine_pool_id: 9, quantity: 7 }],
    })
  })

  it('auto-flow: disables a machine-requiring row no pool covers, with a tooltip naming the methods', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([makePosition({ id: 1 })]) // currentPools is [] (beforeEach)
    detailStore.assignInternal = vi
      .fn<typeof detailStore.assignInternal>()
      .mockResolvedValue(undefined)
    await flushPromises()

    const row = wrapper.get('.row-card')
    expect(row.classes()).toContain('row-card--warning')
    expect(row.find('.warning-badge').exists()).toBe(true)
    expect(row.get('.row-header').classes()).toContain('row-header--disabled')
    // No resolved-pool tag when nothing covers it.
    expect(row.text()).not.toContain('Mill Pool')

    await row.get('.row-header').trigger('click')
    await flushPromises()

    expect(detailStore.assignInternal).not.toHaveBeenCalled()
  })

  it('queues a manual-only position without a machine via the secondary action, even with none selected', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([
      makePosition({
        id: 1,
        quantity: 7,
        quantity_remaining: 7,
        steps: [makeStep({ fabrication_method_requires_machine: false })],
      }),
    ])
    detailStore.assignInternal = vi
      .fn<typeof detailStore.assignInternal>()
      .mockResolvedValue(undefined)
    await flushPromises()

    const queueButton = wrapper.get('.row-secondary button')
    expect(queueButton.attributes('disabled')).toBeUndefined()

    await queueButton.trigger('click')
    await flushPromises()

    expect(detailStore.assignInternal).toHaveBeenCalledWith(1, 1, {
      orders: [{ machine_id: null, quantity: 7 }],
    })
  })

  it('disables "queue without a machine", with a tooltip, for a machine-requiring position', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([makePosition({ id: 1 })]) // default step requires a machine
    await flushPromises()

    const queueButton = wrapper.get('.row-secondary button')
    expect(queueButton.attributes('disabled')).toBeDefined()
    // OpenVue's Tooltip directive (auto-imported per-SFC) only stamps this
    // marker attribute when its bound value is truthy.
    expect(queueButton.attributes('data-pd-tooltip')).toBe('true')
  })

  it('does not queue a machine-requiring position without a machine when clicked while disabled', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([makePosition({ id: 1 })])
    detailStore.assignInternal = vi
      .fn<typeof detailStore.assignInternal>()
      .mockResolvedValue(undefined)
    await flushPromises()

    await wrapper.get('.row-secondary button').trigger('click')
    await flushPromises()

    expect(detailStore.assignInternal).not.toHaveBeenCalled()
  })

  it('shows an internal position with an unassigned order and routes it to a machine', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([
      makePosition({
        id: 1,
        kind: 'internal',
        production_orders: [
          {
            id: 20,
            production_order_number: 'PO-20',
            edit_version: 0,
            status: 'queued',
            priority: 'normal',
            quantity: 5,
            quantity_completed: 0,
            machine_id: null,
            machine_internal_name: '',
            machine_pool_id: null,
            machine_pool_name: '',
            conflicts: ['no_machine_assigned'],
          },
        ],
      }),
    ])
    await flushPromises()

    expect(wrapper.text()).toContain('PO-20')
    const routeRow = wrapper.get('.order-route-row')
    const targetSelect = routeRow.findComponent({ name: 'Select' })
    await targetSelect.vm.$emit('update:modelValue', 'machine:1')
    await flushPromises()

    await routeRow.findComponent({ name: 'Button' }).trigger('click')
    await flushPromises()

    const putMock = (await import('@/core/api')).default.put as ReturnType<typeof vi.fn>
    expect(putMock).toHaveBeenCalledWith('/production-orders/20/machine', { machine_id: 1 })
  })

  it("routes an already-internal position's unassigned order to a pool", async () => {
    currentPools = poolsFixture
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([
      makePosition({
        id: 1,
        kind: 'internal',
        production_orders: [
          {
            id: 20,
            production_order_number: 'PO-20',
            edit_version: 0,
            status: 'queued',
            priority: 'normal',
            quantity: 5,
            quantity_completed: 0,
            machine_id: null,
            machine_internal_name: '',
            machine_pool_id: null,
            machine_pool_name: '',
            conflicts: ['no_machine_assigned'],
          },
        ],
      }),
    ])
    await flushPromises()

    const routeRow = wrapper.get('.order-route-row')
    const targetSelect = routeRow.findComponent({ name: 'Select' })
    await targetSelect.vm.$emit('update:modelValue', 'pool:9')
    await flushPromises()

    await routeRow.findComponent({ name: 'Button' }).trigger('click')
    await flushPromises()

    const putMock = (await import('@/core/api')).default.put as ReturnType<typeof vi.fn>
    expect(putMock).toHaveBeenCalledWith('/production-orders/20/machine', { machine_pool_id: 9 })
  })

  it('does not show a fully-routed internal position in the needs-a-machine section', async () => {
    const { wrapper, detailStore } = mountPanel()
    detailStore.lot = makeLot([
      makePosition({
        id: 1,
        kind: 'internal',
        production_orders: [
          {
            id: 20,
            production_order_number: 'PO-20',
            edit_version: 0,
            status: 'queued',
            priority: 'normal',
            quantity: 5,
            quantity_completed: 0,
            machine_id: 1,
            machine_internal_name: 'Mill A',
            machine_pool_id: null,
            machine_pool_name: '',
            conflicts: [],
          },
        ],
      }),
    ])
    await flushPromises()

    expect(wrapper.find('.order-route-row').exists()).toBe(false)
  })
})
