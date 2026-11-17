import { describe, it, expect } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import type { Ref } from 'vue'
import { createRouter, createMemoryHistory } from 'vue-router'

import { useRouteTab } from '../useRouteTab'

const VALID_TABS = new Set(['first', 'second', 'gated'])

async function mountAt(path: string, isAllowed?: (tab: string) => boolean) {
  const holder: { activeTab?: Ref<string> } = {}
  const Host = defineComponent({
    setup() {
      const activeTab = useRouteTab({
        param: 'tab',
        validTabs: VALID_TABS,
        defaultTab: 'first',
        basePath: '/hub',
        isAllowed,
      })
      holder.activeTab = activeTab
      return () => h('div', activeTab.value)
    },
  })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/hub/:tab?', component: Host }],
  })
  router.push(path)
  await router.isReady()
  mount(Host, { global: { plugins: [router] } })
  return { router, activeTab: () => holder.activeTab! }
}

describe('useRouteTab', () => {
  it('starts from a valid route param', async () => {
    const { activeTab } = await mountAt('/hub/second')

    expect(activeTab().value).toBe('second')
  })

  it('falls back to the default tab for an unknown or missing param', async () => {
    const unknown = await mountAt('/hub/nope')
    const missing = await mountAt('/hub')

    expect(unknown.activeTab().value).toBe('first')
    expect(missing.activeTab().value).toBe('first')
  })

  it('falls back to the default tab when isAllowed rejects the param', async () => {
    const { activeTab } = await mountAt('/hub/gated', (tab) => tab !== 'gated')

    expect(activeTab().value).toBe('first')
  })

  it('replaces the URL when the tab changes', async () => {
    const { router, activeTab } = await mountAt('/hub/first')

    activeTab().value = 'second'
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/hub/second')
  })

  it('follows a route change', async () => {
    const { router, activeTab } = await mountAt('/hub/first')

    await router.push('/hub/second')
    await flushPromises()

    expect(activeTab().value).toBe('second')
  })
})
