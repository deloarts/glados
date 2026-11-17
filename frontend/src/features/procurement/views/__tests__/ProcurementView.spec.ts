import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { asyncTabStub } from '@/test-utils/asyncTabStub'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: [] }),
  },
}))

// The tabs are lazy-loaded via an async tab helper; mock the modules
// behind each tab's dynamic import so this spec exercises the real
// defineAsyncComponent resolution without pulling in each view's own heavy
// dependency tree (stores, OpenVue DataTables, etc).
vi.mock('@/features/orders/views/OrdersView.vue', () => asyncTabStub('OrdersView', '<div>orders-stub</div>'))
vi.mock('@/features/procurement/views/BoughtItemDemandsView.vue', () => asyncTabStub('BoughtItemDemandsView', '<div>bought-items-demand-stub</div>'))
vi.mock('@/features/production/made-item-demands/views/MadeItemDemandsView.vue', () => asyncTabStub('MadeItemDemandsView', '<div>made-items-demand-stub</div>'))
vi.mock('@/features/production/source-item-demands/views/SourceItemDemandsView.vue', () => asyncTabStub('SourceItemDemandsView', '<div>source-items-demand-stub</div>'))

import ProcurementView from '../ProcurementView.vue'

// jsdom does not implement ResizeObserver; OpenVue's TabList binds one in
// its mounted hook to track overflow/scroll buttons.
vi.stubGlobal(
  'ResizeObserver',
  class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
)

function mountAtOrders() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/procurement/:section?/:tab?',
        name: 'Procurement',
        component: ProcurementView,
      },
    ],
  })
  router.push('/procurement/orders')

  return { router }
}

describe('ProcurementView', () => {
  it('mounts with the Orders/Bought Items Demand/Made Items Demand tabs without throwing', async () => {
    const { router } = mountAtOrders()
    await router.isReady()

    const wrapper = mountWithApp(ProcurementView, {
      global: {
        plugins: [router],
      },
    })

    // The active tab (orders) is lazy-loaded, so the dynamic import needs a
    // real macrotask to resolve; poll instead of a fixed wait.
    await vi.waitFor(() => expect(wrapper.findComponent({ name: 'OrdersView' }).exists()).toBe(true), {
      timeout: 2000,
      interval: 25,
    })
    await flushPromises()

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.text()).toContain('Orders')
    expect(wrapper.text()).toContain('Bought Items Demand')
    expect(wrapper.text()).toContain('Made Items Demand')
    expect(wrapper.text()).toContain('Source Items Demand')

    wrapper.unmount()
  })

  it('does not eagerly mount the non-active tabs', async () => {
    const { router } = mountAtOrders()
    await router.isReady()

    const wrapper = mountWithApp(ProcurementView, {
      global: {
        plugins: [router],
      },
    })

    // Right after mount, none of the sibling tabs' components exist at all:
    // their panel is v-if-gated on the active tab, so they are never even
    // requested.
    expect(wrapper.findComponent({ name: 'BoughtItemDemandsView' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'MadeItemDemandsView' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'SourceItemDemandsView' }).exists()).toBe(false)

    await vi.waitFor(() => expect(wrapper.findComponent({ name: 'OrdersView' }).exists()).toBe(true), {
      timeout: 2000,
      interval: 25,
    })

    // Still true once the active tab has resolved.
    expect(wrapper.findComponent({ name: 'BoughtItemDemandsView' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'MadeItemDemandsView' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'SourceItemDemandsView' }).exists()).toBe(false)

    wrapper.unmount()
  })
})
