import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

import { asyncTabStub } from '@/test-utils/asyncTabStub'
import { mountWithApp } from '@/test-utils/mountWithApp'

// The tabs are lazy-loaded (asyncTab helper). This mocks the modules
// behind each tab's dynamic import so this spec exercises the real
// defineAsyncComponent resolution without pulling in each view's own heavy
// dependency tree.
vi.mock('@/features/customers/views/CustomerManagementView.vue', () => asyncTabStub('CustomerManagementView', '<div>customers-stub</div>'))
vi.mock('@/features/suppliers/views/SupplierManagementView.vue', () => asyncTabStub('SupplierManagementView', '<div>suppliers-stub</div>'))
vi.mock('@/features/article-groups/views/ArticleGroupManagementView.vue', () => asyncTabStub('ArticleGroupManagementView', '<div>article-groups-stub</div>'))
vi.mock('@/features/fabrication-method-management/views/FabricationMethodManagementView.vue', () => asyncTabStub('FabricationMethodManagementView', '<div>fabrication-methods-stub</div>'))
vi.mock('@/features/inspection-method-management/views/InspectionMethodManagementView.vue', () => asyncTabStub('InspectionMethodManagementView', '<div>inspection-methods-stub</div>'))
vi.mock('@/features/source-item-types/views/SourceItemTypeManagementView.vue', () => asyncTabStub('SourceItemTypeManagementView', '<div>source-item-types-stub</div>'))
vi.mock('@/features/production-machines/views/ProductionMachinesView.vue', () => asyncTabStub('ProductionMachinesView', '<div>machines-stub</div>'))
vi.mock('@/features/production-machines/views/MachinePoolManagementView.vue', () => asyncTabStub('MachinePoolManagementView', '<div>machine-pools-stub</div>'))
vi.mock('@/features/holidays/views/HolidayManagementView.vue', () => asyncTabStub('HolidayManagementView', '<div>holidays-stub</div>'))
vi.mock('@/features/printers/views/PrinterManagementView.vue', () => asyncTabStub('PrinterManagementView', '<div>printers-stub</div>'))
vi.mock('@/features/print-labels/views/PrintLabelManagementView.vue', () => asyncTabStub('PrintLabelManagementView', '<div>print-labels-stub</div>'))
vi.mock('@/features/print-dockets/views/PrintDocketManagementView.vue', () => asyncTabStub('PrintDocketManagementView', '<div>print-dockets-stub</div>'))
vi.mock('@/features/terminals/views/TerminalsView.vue', () => asyncTabStub('TerminalsView', '<div>terminals-stub</div>'))
vi.mock('@/features/infoscreens/views/InfoscreensView.vue', () => asyncTabStub('InfoscreensView', '<div>infoscreens-stub</div>'))

import ResourcesView from '../ResourcesView.vue'

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

function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/resources/:tab?', name: 'Resources', component: ResourcesView }],
  })
  router.push(path)
  return router
}

describe('ResourcesView', () => {
  it('defaults to the customers tab and lazy-loads it without throwing', async () => {
    const router = mountAt('/resources/customers')
    await router.isReady()

    const wrapper = mountWithApp(ResourcesView, { global: { plugins: [router] } })

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'CustomerManagementView' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    await flushPromises()

    expect(wrapper.text()).toContain('Customers')
    expect(wrapper.text()).toContain('Suppliers')
    expect(wrapper.text()).toContain('Printers')

    wrapper.unmount()
  })

  it('does not eagerly mount any non-active tab, including the production-machines ones', async () => {
    const router = mountAt('/resources/customers')
    await router.isReady()

    const wrapper = mountWithApp(ResourcesView, { global: { plugins: [router] } })

    expect(wrapper.findComponent({ name: 'SupplierManagementView' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'ProductionMachinesView' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'MachinePoolManagementView' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'PrintDocketManagementView' }).exists()).toBe(false)

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'CustomerManagementView' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )

    expect(wrapper.findComponent({ name: 'SupplierManagementView' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('switches to the machine-pools tab straight from the route param', async () => {
    const router = mountAt('/resources/machine-pools')
    await router.isReady()

    const wrapper = mountWithApp(ResourcesView, { global: { plugins: [router] } })

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'MachinePoolManagementView' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    expect(wrapper.findComponent({ name: 'CustomerManagementView' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('opens the holidays tab straight from the route param', async () => {
    const router = mountAt('/resources/holidays')
    await router.isReady()

    const wrapper = mountWithApp(ResourcesView, { global: { plugins: [router] } })

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'HolidayManagementView' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    expect(wrapper.text()).toContain('Holidays')

    wrapper.unmount()
  })

  it('opens the terminals and infoscreens tabs straight from the route param', async () => {
    for (const [path, name] of [
      ['/resources/terminals', 'TerminalsView'],
      ['/resources/infoscreens', 'InfoscreensView'],
    ] as const) {
      const router = mountAt(path)
      await router.isReady()

      const wrapper = mountWithApp(ResourcesView, { global: { plugins: [router] } })

      await vi.waitFor(() => expect(wrapper.findComponent({ name }).exists()).toBe(true), {
        timeout: 2000,
        interval: 25,
      })
      expect(wrapper.text()).toContain('Terminals')
      expect(wrapper.text()).toContain('Infoscreens')

      wrapper.unmount()
    }
  })

  it('falls back to the customers tab for an unknown :tab route param', async () => {
    const router = mountAt('/resources/not-a-real-tab')
    await router.isReady()

    const wrapper = mountWithApp(ResourcesView, { global: { plugins: [router] } })

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'CustomerManagementView' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )

    wrapper.unmount()
  })
})
