import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

import { asyncTabStub } from '@/test-utils/asyncTabStub'
import { mountWithApp } from '@/test-utils/mountWithApp'

// The tabs are lazy-loaded via the asyncTab helper. Mock the modules
// behind each tab's dynamic import so this spec exercises the real
// defineAsyncComponent resolution without pulling in each view's own heavy
// dependency tree (stores, OpenVue DataTables, etc).
vi.mock('@/features/bought-items/views/BoughtItemCatalogueView.vue', () => asyncTabStub('BoughtItemCatalogueView', '<div>bought-items-catalogue-stub</div>'))
vi.mock('@/features/made-items/views/MadeItemCatalogueView.vue', () => asyncTabStub('MadeItemCatalogueView', '<div>made-items-catalogue-stub</div>'))
vi.mock('@/features/source-items/views/SourceItemCatalogueView.vue', () => asyncTabStub('SourceItemCatalogueView', '<div>source-items-catalogue-stub</div>'))

import CatalogueView from '../CatalogueView.vue'

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
    routes: [{ path: '/catalogue/:tab?', name: 'Catalogue', component: CatalogueView }],
  })
  router.push(path)
  return router
}

describe('CatalogueView', () => {
  it('defaults to the bought-items tab and lazy-loads it without throwing', async () => {
    const router = mountAt('/catalogue/bought-items')
    await router.isReady()

    const wrapper = mountWithApp(CatalogueView, { global: { plugins: [router] } })

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'BoughtItemCatalogueView' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    await flushPromises()

    expect(wrapper.text()).toContain('Bought Items')
    expect(wrapper.text()).toContain('Made Items')
    expect(wrapper.text()).toContain('Source Items')

    wrapper.unmount()
  })

  it('does not eagerly mount the non-active tabs', async () => {
    const router = mountAt('/catalogue/bought-items')
    await router.isReady()

    const wrapper = mountWithApp(CatalogueView, { global: { plugins: [router] } })

    expect(wrapper.findComponent({ name: 'MadeItemCatalogueView' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'SourceItemCatalogueView' }).exists()).toBe(false)

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'BoughtItemCatalogueView' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )

    expect(wrapper.findComponent({ name: 'MadeItemCatalogueView' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'SourceItemCatalogueView' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('falls back to the bought-items tab for an unknown :tab route param', async () => {
    const router = mountAt('/catalogue/not-a-real-tab')
    await router.isReady()

    const wrapper = mountWithApp(CatalogueView, { global: { plugins: [router] } })

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'BoughtItemCatalogueView' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )

    wrapper.unmount()
  })
})
