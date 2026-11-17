import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useLeaveGuard } from '../useLeaveGuard'

const dirty = ref(false)
const confirm = vi.fn<() => Promise<boolean>>()
let guard: ReturnType<typeof useLeaveGuard> | null = null

const Page = defineComponent({
  setup() {
    guard = useLeaveGuard({ dirty: () => dirty.value, confirm, updates: true })
    return () => h('div', 'page')
  },
})

async function mountAt(path: string) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = { id: 1, permissions: [], is_systemuser: false } as never
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/page/:id', component: Page },
      { path: '/elsewhere', component: { render: () => h('div', 'elsewhere') } },
      { path: '/login', name: 'Login', component: { render: () => h('div', 'login') } },
    ],
  })
  router.push(path)
  await router.isReady()
  const wrapper = mount(RouterView, { global: { plugins: [router, pinia] } })
  await flushPromises()
  return { router, wrapper }
}

describe('useLeaveGuard', () => {
  beforeEach(() => {
    dirty.value = false
    confirm.mockReset()
  })

  it('lets a page without changes go unasked', async () => {
    const { router } = await mountAt('/page/1')
    await router.push('/elsewhere')
    expect(confirm).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/elsewhere')
  })

  it('asks before leaving or opening another document with changes, and stays when cancelled', async () => {
    const { router } = await mountAt('/page/1')
    dirty.value = true
    confirm.mockResolvedValue(false)

    await router.push('/page/2')
    await router.push('/elsewhere')
    expect(confirm).toHaveBeenCalledTimes(2)
    expect(router.currentRoute.value.path).toBe('/page/1')

    confirm.mockResolvedValue(true)
    await router.push('/elsewhere')
    expect(router.currentRoute.value.path).toBe('/elsewhere')
  })

  it('lets the redirect after the session ended through, and a navigation the page allowed', async () => {
    const { router } = await mountAt('/page/1')
    dirty.value = true

    guard?.allowNext()
    await router.push('/page/2')
    expect(confirm).not.toHaveBeenCalled()

    useCurrentUserStore().user = null
    await router.push('/login')
    expect(confirm).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('has the browser ask before the tab closes with changes', async () => {
    const { wrapper } = await mountAt('/page/1')
    const clean = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(clean)
    expect(clean.defaultPrevented).toBe(false)

    dirty.value = true
    const withChanges = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(withChanges)
    expect(withChanges.defaultPrevented).toBe(true)

    wrapper.unmount()
  })
})
