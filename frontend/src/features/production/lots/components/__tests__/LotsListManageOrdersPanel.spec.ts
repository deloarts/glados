import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderResponse } from '@/test-utils/factories'
import { useProductionLotsSelectionStore } from '../../stores/productionLotsSelectionStore'
import { useProductionLotsStore } from '../../../stores/productionLotsStore'

import { makePosition } from '../../__tests__/fixtures'

const getMock = vi.fn<() => Promise<unknown>>().mockResolvedValue({
  data: { items: [], total: 0, limit: 1000, skip: 0 },
})
const postMock = vi
  .fn<(url: string, payload: unknown) => Promise<unknown>>()
  .mockResolvedValue({ data: {} })

vi.mock('@/core/api', () => ({
  default: {
    get: () => getMock(),
    post: (url: string, payload: unknown) => postMock(url, payload),
  },
}))

import LotsListManageOrdersPanel from '../LotsListManageOrdersPanel.vue'

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(LotsListManageOrdersPanel, {
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

describe('LotsListManageOrdersPanel', () => {
  beforeEach(() => {
    postMock.mockClear()
    postMock.mockResolvedValue({ data: {} })
  })

  it('shows the empty state when nothing is selected', () => {
    const { wrapper } = mountPanel()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('renders one row per selected step, across lots', async () => {
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
        lotId: 2,
        lotNumber: 'LOT-2',
        projectId: 200,
        madeItemPartNumber: 'PN-2',
        position: makePosition({ id: 2, lot_id: 2 }),
      },
    ]
    await flushPromises()

    expect(wrapper.findAll('.row-card')).toHaveLength(2)
  })

  it('removes a row via the remove button without an API call', async () => {
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

    await wrapper.get('.row-header button').trigger('click')

    expect(selectionStore.items).toHaveLength(0)
    expect(postMock).not.toHaveBeenCalled()
  })

  it('assigns every selected step to the chosen order with unit hardcoded to PCS', async () => {
    const { wrapper, selectionStore, lotsStore } = mountPanel()
    lotsStore.triggerRefresh = vi.fn<() => void>()
    selectionStore.selectedOrder = makeOrderResponse({ id: 9 })
    selectionStore.items = [
      {
        lotId: 1,
        lotNumber: 'LOT-1',
        projectId: 100,
        madeItemPartNumber: 'PN-1',
        position: makePosition({ id: 1 }),
      },
      {
        lotId: 2,
        lotNumber: 'LOT-2',
        projectId: 200,
        madeItemPartNumber: 'PN-2',
        position: makePosition({ id: 2, lot_id: 2, sequence: 2 }),
      },
    ]
    await flushPromises()

    await wrapper.get('.panel-footer button').trigger('click')
    await flushPromises()

    expect(postMock).toHaveBeenCalledWith(
      '/production-lots/1/positions/1/assign',
      expect.objectContaining({ order_id: 9, unit: 'PCS', items_per_unit: 1 }),
    )
    expect(postMock).toHaveBeenCalledWith(
      '/production-lots/2/positions/2/assign',
      expect.objectContaining({ order_id: 9, unit: 'PCS', items_per_unit: 1 }),
    )
    expect(selectionStore.items).toHaveLength(0)
    expect(lotsStore.triggerRefresh).toHaveBeenCalled()
    expect(wrapper.emitted('assigned')).toHaveLength(1)
  })

  it('keeps failed rows and reports an error on partial failure', async () => {
    postMock.mockImplementation((url: string) =>
      url.includes('/positions/1/')
        ? Promise.reject(new Error('boom'))
        : Promise.resolve({ data: {} }),
    )
    const { wrapper, selectionStore } = mountPanel()
    selectionStore.selectedOrder = makeOrderResponse({ id: 9 })
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
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(wrapper.emitted('assigned')).toBeUndefined()
  })

  it('disables the assign button until an order is selected', async () => {
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

    expect(wrapper.get('.panel-footer button').attributes('disabled')).toBeDefined()
  })

  it('opens the manage-orders handbook doc from the header', async () => {
    // A real router here rather than the RouterLink stub: the handbook drawer
    // links back to the doc's own page, so it needs routes to resolve.
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'Home', component: { template: '<div />' } },
        {
          path: '/handbook/:section/:page',
          name: 'HandbookPage',
          component: { template: '<div />' },
        },
      ],
    })
    await router.push('/')
    await router.isReady()

    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mountWithApp(LotsListManageOrdersPanel, {
      pinia,
      global: {
        plugins: [router],
      },
      attachTo: document.body,
    })
    await flushPromises()

    const explain = wrapper.get('.panel-header-row').findComponent({ name: 'Button' })
    expect(explain.props('icon')).toBe('mdi mdi-help-circle-outline')
    await explain.trigger('click')

    // The doc is a lazily-imported chunk, so wait for it rather than a tick.
    await vi.waitFor(() => {
      expect(document.querySelector('.handbook-prose')).not.toBeNull()
    })
    expect(document.body.textContent).toContain('Manage Orders')
    expect(document.body.textContent).toContain('Which steps you can click')

    wrapper.unmount()
    document.body.innerHTML = ''
  })
})
