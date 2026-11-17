import { describe, it, expect, vi } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'

import { asyncTabStub } from '@/test-utils/asyncTabStub'
import { mountWithApp } from '@/test-utils/mountWithApp'

// The tabs are lazy-loaded through asyncTab; mock them so this spec checks the
// tab shell, not the tables.
vi.mock('@/features/tools/components/GeneralTolerancesTab.vue', () => asyncTabStub('GeneralTolerancesTab', '<div>general-tolerances-stub</div>'))
vi.mock('@/features/tools/components/ThreadsTab.vue', () => asyncTabStub('ThreadsTab', '<div>threads-stub</div>'))

import TablesView from '../TablesView.vue'

// jsdom does not implement ResizeObserver; OpenVue's TabList binds one.
vi.stubGlobal(
  'ResizeObserver',
  class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
)

async function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/tables/:tab?', name: 'Tables', component: TablesView }],
  })
  router.push(path)
  await router.isReady()
  const wrapper = mountWithApp(TablesView, { global: { plugins: [router] } })
  return { router, wrapper }
}

describe('TablesView', () => {
  it('opens the general tolerances by default and offers the thread table', async () => {
    const { wrapper } = await mountAt('/tables')

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'GeneralTolerancesTab' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    expect(wrapper.text()).toContain('General tolerances')
    expect(wrapper.text()).toContain('Threads')
    expect(wrapper.text()).not.toContain('Fit calculator')
    wrapper.unmount()
  })

  it('opens a table from the route and switches tabs through the route', async () => {
    const { router, wrapper } = await mountAt('/tables/threads')

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'ThreadsTab' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    expect(wrapper.findComponent({ name: 'GeneralTolerancesTab' }).exists()).toBe(false)

    await wrapper.get('[data-testid="tables-tab-general-tolerances"]').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/tables/general-tolerances'), {
      timeout: 2000,
      interval: 25,
    })
    wrapper.unmount()
  })

  it('falls back to the first table for an unknown tab', async () => {
    const { wrapper } = await mountAt('/tables/unknown')

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'GeneralTolerancesTab' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    wrapper.unmount()
  })
})
