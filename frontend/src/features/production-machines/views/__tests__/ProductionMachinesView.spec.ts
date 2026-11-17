import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import ConfirmationService from 'openvue/confirmationservice'

import type { ProductionMachineResponse } from '../../types/productionMachinesResponse'

// ProductionMachinesTable owns its own store/fetch (useProductionMachinesStore,
// already covered by its own dedicated spec) and is heavy DataTable
// machinery this view itself has no stake in, so it is replaced with a stub that
// exposes exactly the contract ProductionMachinesView reads from it (its own
// `refresh`, via defineExpose in ProductionMachinesTable.vue), mirroring
// LotDetailView.spec.ts's stubbing of LotDetailContent.
const refreshMock = vi.fn<() => void>()
vi.mock('../../components/ProductionMachinesTable.vue', async () => {
  const { defineComponent, h } = await import('vue')
  const TableStub = defineComponent({
    name: 'ProductionMachinesTable',
    emits: ['edit', 'manage-calendar'],
    setup(_, { expose }) {
      expose({ refresh: refreshMock })
      return () => h('div', { class: 'production-machines-table-stub' })
    },
  })
  return { default: TableStub }
})

function makeMachine(overrides: Partial<ProductionMachineResponse> = {}): ProductionMachineResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    archived: false,
    created: '2026-07-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    internal_name: 'Mill A',
    vendor: 'Acme',
    model: 'M1',
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

import ProductionMachinesView from '../ProductionMachinesView.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

const mounted: VueWrapper[] = []

function mountView() {
  const wrapper = mountWithApp(ProductionMachinesView, {
    global: {
      plugins: [ConfirmationService],
      stubs: {
        ProductionMachinesControls: true,
        ProductionMachinesViews: true,
        ProductionMachineFormDialog: true,
        MachineCalendarDialog: true,
        DefaultCalendarDialog: true,
      },
    },
  })
  mounted.push(wrapper)
  return wrapper
}

describe('ProductionMachinesView', () => {
  beforeEach(() => {
    refreshMock.mockReset()
  })

  afterEach(() => {
    for (const wrapper of mounted) wrapper.unmount()
    mounted.length = 0
  })

  // This view has no fetch of its own; ProductionMachinesTable (stubbed
  // above) owns the load entirely via useServerTable's own onMounted hook.

  it('opens the form dialog with no machine when Controls emits create', async () => {
    const wrapper = mountView()

    expect(wrapper.findComponent({ name: 'ProductionMachineFormDialog' }).props('visible')).toBe(
      false,
    )

    wrapper.findComponent({ name: 'ProductionMachinesControls' }).vm.$emit('create')
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'ProductionMachineFormDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('machine')).toBeNull()
  })

  it('opens the default calendar dialog when Controls emits default-calendar', async () => {
    const wrapper = mountView()

    expect(wrapper.findComponent({ name: 'DefaultCalendarDialog' }).props('visible')).toBe(false)

    wrapper.findComponent({ name: 'ProductionMachinesControls' }).vm.$emit('default-calendar')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'DefaultCalendarDialog' }).props('visible')).toBe(true)
  })

  it('opens the form dialog with the target machine when the table emits edit', async () => {
    const wrapper = mountView()
    const machine = makeMachine({ id: 4, internal_name: 'Mill B' })

    wrapper.findComponent({ name: 'ProductionMachinesTable' }).vm.$emit('edit', machine)
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'ProductionMachineFormDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('machine')).toMatchObject({ id: 4, internal_name: 'Mill B' })
  })

  it('opens the machine calendar dialog when the table emits manage-calendar', async () => {
    const wrapper = mountView()
    const machine = makeMachine({ id: 5, internal_name: 'Mill C' })

    wrapper.findComponent({ name: 'ProductionMachinesTable' }).vm.$emit('manage-calendar', machine)
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'MachineCalendarDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('machine')).toMatchObject({ id: 5, internal_name: 'Mill C' })
  })

  it('refreshes the table when the form dialog reports saved', async () => {
    const wrapper = mountView()

    wrapper.findComponent({ name: 'ProductionMachineFormDialog' }).vm.$emit('saved')
    await flushPromises()

    expect(refreshMock).toHaveBeenCalledTimes(1)
  })

  it('mounts no ConfirmDialog of its own, since App.vue hosts the one every confirmation uses', () => {
    const wrapper = mountView()

    expect(wrapper.findComponent({ name: 'ConfirmDialog' }).exists()).toBe(false)
  })
})
