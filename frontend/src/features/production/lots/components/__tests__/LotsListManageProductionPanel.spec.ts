import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { useProductionLotsSelectionStore } from '../../stores/productionLotsSelectionStore'
import { useProductionLotsStore } from '../../../stores/productionLotsStore'

import type { ProductionMachineResponse } from '@/features/production-machines'
import type { MachinePoolResponse } from '@/features/production-machines'
import { makePosition } from '../../__tests__/fixtures'

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
  ]
  // Covers fabrication method 1 only (Mill A's): the auto-flow tests' "one
  // covering pool" fixture. Left out of currentPools by default so every
  // other test's machine-requiring positions still see "no covering pool",
  // same as before pools existed. Opted into explicitly per test.
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

let currentPools: MachinePoolResponse[] = []
let currentMachines: ProductionMachineResponse[] = machinesFixture

const postMock = vi
  .fn<(url: string, payload: unknown) => Promise<unknown>>()
  .mockResolvedValue({ data: {} })
const putMock = vi
  .fn<(url: string, payload: unknown) => Promise<unknown>>()
  .mockResolvedValue({ data: {} })

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<(url: string) => Promise<unknown>>().mockImplementation((url: string) => {
      if (url === '/production-machine-pools/') {
        return Promise.resolve({
          data: { items: currentPools, total: currentPools.length, limit: 500, skip: 0 },
        })
      }
      return Promise.resolve({
        data: { items: currentMachines, total: currentMachines.length, limit: 200, skip: 0 },
      })
    }),
    post: (url: string, payload: unknown) => postMock(url, payload),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import LotsListManageProductionPanel from '../LotsListManageProductionPanel.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(LotsListManageProductionPanel, {
    pinia,
    global: {
      stubs: { RouterLink: true },
    },
  })
  return {
    wrapper,
    selectionStore: useProductionLotsSelectionStore(),
    lotsStore: useProductionLotsStore(),
  }
}

describe('LotsListManageProductionPanel', () => {
  beforeEach(() => {
    postMock.mockClear()
    putMock.mockClear()
    postMock.mockResolvedValue({ data: {} })
    putMock.mockResolvedValue({ data: {} })
    currentPools = []
    currentMachines = machinesFixture
  })

  it('shows the empty state when nothing is selected', () => {
    const { wrapper } = mountPanel()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('offers no archived machine or pool as a target, since neither takes work', async () => {
    currentMachines = [
      ...machinesFixture,
      { ...machinesFixture[0]!, id: 2, internal_name: 'Old Mill', archived: true },
    ]
    currentPools = [...poolsFixture, { ...poolsFixture[0]!, id: 10, name: 'Old Pool', archived: true }]
    const { wrapper } = mountPanel()
    await flushPromises()

    const groups = wrapper.findComponent({ name: 'Select' }).props('options') as {
      items: { label: string }[]
    }[]
    expect(groups.flatMap((group) => group.items.map((item) => item.label))).toEqual([
      'Mill Pool',
      'Mill A',
    ])
  })

  it('assigns fresh-unassigned rows with the selected machine', async () => {
    const { wrapper, selectionStore, lotsStore } = mountPanel()
    lotsStore.triggerRefresh = vi.fn<() => void>()
    selectionStore.selectedMachine = machinesFixture[0]!
    await flushPromises()
    selectionStore.items = [
      {
        lotId: 1,
        lotNumber: 'LOT-1',
        projectId: 100,
        madeItemPartNumber: 'PN-1',
        position: makePosition({ id: 1, quantity: 7, quantity_remaining: 7 }),
      },
    ]
    await flushPromises()

    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(postMock).toHaveBeenCalledWith('/production-lots/1/positions/1/assign-internal', {
      orders: [{ machine_id: 1, quantity: 7 }],
    })
    expect(selectionStore.items).toHaveLength(0)
    expect(lotsStore.triggerRefresh).toHaveBeenCalled()
    expect(wrapper.emitted('assigned')).toHaveLength(1)
  })

  // Manual-only (no machine-requiring step): the auto-flow only ever
  // resolves a pool for a row that actually needs a machine, a manual
  // position keeps today's plain "queue without a machine" behaviour.
  it('queues without a machine when none is selected, for a manual-only position', async () => {
    const { wrapper, selectionStore } = mountPanel()
    selectionStore.items = [
      {
        lotId: 1,
        lotNumber: 'LOT-1',
        projectId: 100,
        madeItemPartNumber: 'PN-1',
        position: makePosition({
          id: 1,
          quantity: 7,
          quantity_remaining: 7,
          steps: [
            {
              ...makePosition().steps![0]!,
              fabrication_method_requires_machine: false,
            },
          ],
        }),
      },
    ]
    await flushPromises()

    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(postMock).toHaveBeenCalledWith('/production-lots/1/positions/1/assign-internal', {
      orders: [{ machine_id: null, quantity: 7 }],
    })
  })

  it('auto-flow: shows the resolved-pool tag and submits machine_pool_id when no target is picked', async () => {
    currentPools = poolsFixture
    const { wrapper, selectionStore } = mountPanel()
    selectionStore.items = [
      {
        lotId: 1,
        lotNumber: 'LOT-1',
        projectId: 100,
        madeItemPartNumber: 'PN-1',
        position: makePosition({ id: 1, quantity: 7, quantity_remaining: 7 }),
      },
    ]
    await flushPromises()

    const row = wrapper.get('.row-card')
    expect(row.text()).toContain('Mill Pool')
    expect(row.classes()).not.toContain('row-card--disabled')

    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(postMock).toHaveBeenCalledWith('/production-lots/1/positions/1/assign-internal', {
      orders: [{ machine_pool_id: 9, quantity: 7 }],
    })
    expect(selectionStore.items).toHaveLength(0)
  })

  it('auto-flow: disables and excludes from submit a row no pool covers', async () => {
    const { wrapper, selectionStore } = mountPanel()
    selectionStore.items = [
      {
        lotId: 1,
        lotNumber: 'LOT-1',
        projectId: 100,
        madeItemPartNumber: 'PN-1',
        position: makePosition({ id: 1, quantity: 7, quantity_remaining: 7 }),
      },
    ]
    await flushPromises()

    const row = wrapper.get('.row-card')
    expect(row.classes()).toContain('row-card--disabled')
    expect(row.find('.no-pool-icon').exists()).toBe(true)

    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(postMock).not.toHaveBeenCalled()
    // Stays in the list, not silently dropped.
    expect(selectionStore.items).toHaveLength(1)
  })

  it("routes an already-internal row's unassigned orders to the selected machine", async () => {
    const { wrapper, selectionStore } = mountPanel()
    selectionStore.selectedMachine = machinesFixture[0]!
    await flushPromises()
    selectionStore.items = [
      {
        lotId: 1,
        lotNumber: 'LOT-1',
        projectId: 100,
        madeItemPartNumber: 'PN-1',
        position: makePosition({
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
      },
    ]
    await flushPromises()

    expect(wrapper.text()).toContain('PO-20')

    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith('/production-orders/20/machine', { machine_id: 1 })
    expect(selectionStore.items).toHaveLength(0)
  })

  it('clears the batch when the selected machine changes', async () => {
    const { wrapper, selectionStore } = mountPanel()
    selectionStore.items = [
      {
        lotId: 1,
        lotNumber: 'LOT-1',
        projectId: 100,
        madeItemPartNumber: 'PN-1',
        position: makePosition({ id: 1 }),
      },
    ]
    await flushPromises()
    expect(selectionStore.items).toHaveLength(1)

    const targetSelect = wrapper.findComponent({ name: 'Select' })
    await targetSelect.vm.$emit('update:modelValue', `machine:${machinesFixture[0]!.id}`)
    await flushPromises()

    expect(selectionStore.selectedMachine).toEqual(machinesFixture[0])
    expect(selectionStore.items).toHaveLength(0)
  })

  it('keeps failed rows and reports an error on partial failure', async () => {
    // Both rows need a resolvable pool to actually reach the API call;
    // without one they'd be excluded from submit entirely, which
    // would make this test's failure/success split meaningless.
    currentPools = poolsFixture
    postMock.mockImplementation((url: string) =>
      url.includes('/positions/1/')
        ? Promise.reject(new Error('boom'))
        : Promise.resolve({ data: {} }),
    )
    const { wrapper, selectionStore } = mountPanel()
    selectionStore.items = [
      {
        lotId: 1,
        lotNumber: 'LOT-1',
        projectId: 100,
        madeItemPartNumber: 'PN-1',
        position: makePosition({ id: 1 }),
      },
      {
        lotId: 1,
        lotNumber: 'LOT-1',
        projectId: 100,
        madeItemPartNumber: 'PN-1',
        position: makePosition({ id: 2, sequence: 2 }),
      },
    ]
    await flushPromises()

    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(selectionStore.items).toHaveLength(1)
    expect(selectionStore.items[0]!.position.id).toBe(1)
    expect(wrapper.find('[data-testid="manage-production-error"]').exists()).toBe(true)
    expect(wrapper.emitted('assigned')).toBeUndefined()
  })
})
