import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import ConfirmationService from 'openvue/confirmationservice'

import type { MachinePoolResponse } from '../../types/machinePoolsResponse'

// MachinePoolsTable owns its own store/fetch (useMachinePoolsStore, already
// exercised for real elsewhere) and is heavy DataTable machinery this view
// itself has no stake in, so it is replaced with a stub that exposes exactly the
// contract MachinePoolManagementView reads from it (its own `refresh`,
// via defineExpose in MachinePoolsTable.vue), mirroring
// LotDetailView.spec.ts's stubbing of LotDetailContent.
const refreshMock = vi.fn<() => void>()
vi.mock('../../components/MachinePoolsTable.vue', async () => {
  const { defineComponent, h } = await import('vue')
  const TableStub = defineComponent({
    name: 'MachinePoolsTable',
    emits: ['edit'],
    setup(_, { expose }) {
      expose({ refresh: refreshMock })
      return () => h('div', { class: 'machine-pools-table-stub' })
    },
  })
  return { default: TableStub }
})

function makePool(overrides: Partial<MachinePoolResponse> = {}): MachinePoolResponse {
  return {
    id: 7,
    public_id: '33333333-3333-3333-3333-333333333333',
    archived: false,
    created: '2026-07-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    name: 'Mill Pool',
    machine_ids: [1, 2],
    machines: [],
    note: null,
    creator_id: 1,
    creator_full_name: 'Tester',
    changes: [],
    ...overrides,
  }
}

import MachinePoolManagementView from '../MachinePoolManagementView.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

const mounted: VueWrapper[] = []

function mountView() {
  const wrapper = mountWithApp(MachinePoolManagementView, {
    global: {
      plugins: [ConfirmationService],
      stubs: {
        MachinePoolsControls: true,
        MachinePoolsViews: true,
        MachinePoolFormDialog: true,
      },
    },
  })
  mounted.push(wrapper)
  return wrapper
}

describe('MachinePoolManagementView', () => {
  beforeEach(() => {
    refreshMock.mockReset()
  })

  afterEach(() => {
    for (const wrapper of mounted) wrapper.unmount()
    mounted.length = 0
  })

  // This view has no fetch of its own; MachinePoolsTable (stubbed above)
  // owns the load entirely via useServerTable's own onMounted hook. Nothing
  // here for the view itself to trigger.

  it('opens the form dialog with no pool when Controls emits create', async () => {
    const wrapper = mountView()

    let dialog = wrapper.findComponent({ name: 'MachinePoolFormDialog' })
    expect(dialog.props('visible')).toBe(false)

    wrapper.findComponent({ name: 'MachinePoolsControls' }).vm.$emit('create')
    await flushPromises()

    dialog = wrapper.findComponent({ name: 'MachinePoolFormDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('pool')).toBeNull()
  })

  it('opens the form dialog with the target pool when the table emits edit', async () => {
    const wrapper = mountView()
    const pool = makePool({ id: 9, name: 'Turning Pool' })

    wrapper.findComponent({ name: 'MachinePoolsTable' }).vm.$emit('edit', pool)
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'MachinePoolFormDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('pool')).toMatchObject({ id: 9, name: 'Turning Pool' })
  })

  it('refreshes the table when the form dialog reports saved', async () => {
    const wrapper = mountView()

    wrapper.findComponent({ name: 'MachinePoolFormDialog' }).vm.$emit('saved')
    await flushPromises()

    expect(refreshMock).toHaveBeenCalledTimes(1)
  })

  it('mounts no ConfirmDialog of its own, since App.vue hosts the one every confirmation uses', () => {
    const wrapper = mountView()

    expect(wrapper.findComponent({ name: 'ConfirmDialog' }).exists()).toBe(false)
  })
})
