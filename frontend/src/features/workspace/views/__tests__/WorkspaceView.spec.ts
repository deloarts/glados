import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

import { asyncTabStub } from '@/test-utils/asyncTabStub'
import { mountWithApp } from '@/test-utils/mountWithApp'

// The tabs are lazy-loaded (the asyncTab helper); mock the modules
// behind each tab's dynamic import so this spec exercises the real
// defineAsyncComponent resolution without pulling in each view's own heavy
// dependency tree.
vi.mock('@/features/products/views/ProductsManagementView.vue', () => asyncTabStub('ProductsManagementView', '<div>products-stub</div>'))
vi.mock('@/features/projects/views/ProjectsManagementView.vue', () => asyncTabStub('ProjectsManagementView', '<div>projects-stub</div>'))

import WorkspaceView from '../WorkspaceView.vue'

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
    routes: [{ path: '/workspace/:tab?', name: 'Workspace', component: WorkspaceView }],
  })
  router.push(path)
  return router
}

describe('WorkspaceView', () => {
  it('defaults to the products tab and lazy-loads it without throwing', async () => {
    const router = mountAt('/workspace/products')
    await router.isReady()

    const wrapper = mountWithApp(WorkspaceView, { global: { plugins: [router] } })

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'ProductsManagementView' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    await flushPromises()

    expect(wrapper.text()).toContain('Products')
    expect(wrapper.text()).toContain('Projects')

    wrapper.unmount()
  })

  it('does not eagerly mount the non-active tab', async () => {
    const router = mountAt('/workspace/products')
    await router.isReady()

    const wrapper = mountWithApp(WorkspaceView, { global: { plugins: [router] } })

    expect(wrapper.findComponent({ name: 'ProjectsManagementView' }).exists()).toBe(false)

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'ProductsManagementView' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )

    expect(wrapper.findComponent({ name: 'ProjectsManagementView' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('switches to the projects tab straight from the route param', async () => {
    const router = mountAt('/workspace/projects')
    await router.isReady()

    const wrapper = mountWithApp(WorkspaceView, { global: { plugins: [router] } })

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'ProjectsManagementView' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    expect(wrapper.findComponent({ name: 'ProductsManagementView' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('falls back to the products tab for an unknown :tab route param', async () => {
    const router = mountAt('/workspace/not-a-real-tab')
    await router.isReady()

    const wrapper = mountWithApp(WorkspaceView, { global: { plugins: [router] } })

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'ProductsManagementView' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )

    wrapper.unmount()
  })
})
