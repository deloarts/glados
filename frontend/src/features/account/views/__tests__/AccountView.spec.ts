import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

import { asyncTabStub } from '@/test-utils/asyncTabStub'
import { mountWithApp } from '@/test-utils/mountWithApp'

// The tabs are lazy-loaded (via the asyncTab helper), so mock the modules
// behind each tab's dynamic import so this spec exercises the real
// defineAsyncComponent resolution without pulling in each view's own heavy
// dependency tree.
vi.mock('../AccountMeView.vue', () => asyncTabStub('AccountMeView', '<div>me-stub</div>'))
vi.mock('../AccountNotificationsView.vue', () => asyncTabStub('AccountNotificationsView', '<div>notifications-stub</div>'))
vi.mock('../AccountAccessTokenView.vue', () => asyncTabStub('AccountAccessTokenView', '<div>pat-stub</div>'))
vi.mock('@/features/auth/views/TwoFactorView.vue', () => asyncTabStub('TwoFactorView', '<div>2fa-stub</div>'))
vi.mock('../AccountSessionsView.vue', () => asyncTabStub('AccountSessionsView', '<div>sessions-stub</div>'))
vi.mock('../AccountPermissionsView.vue', () => asyncTabStub('AccountPermissionsView', '<div>permissions-stub</div>'))

import AccountView from '../AccountView.vue'

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
    routes: [{ path: '/account/:tab?', name: 'Account', component: AccountView }],
  })
  router.push(path)
  return router
}

describe('AccountView', () => {
  it('defaults to the me tab and lazy-loads it without throwing', async () => {
    const router = mountAt('/account/me')
    await router.isReady()

    const wrapper = mountWithApp(AccountView, { global: { plugins: [router] } })

    await vi.waitFor(() => expect(wrapper.findComponent({ name: 'AccountMeView' }).exists()).toBe(true), {
      timeout: 2000,
      interval: 25,
    })
    await flushPromises()

    expect(wrapper.exists()).toBe(true)

    wrapper.unmount()
  })

  it('does not eagerly mount the non-active tabs', async () => {
    const router = mountAt('/account/me')
    await router.isReady()

    const wrapper = mountWithApp(AccountView, { global: { plugins: [router] } })

    expect(wrapper.findComponent({ name: 'AccountNotificationsView' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'AccountAccessTokenView' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'TwoFactorView' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'AccountSessionsView' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'AccountPermissionsView' }).exists()).toBe(false)

    await vi.waitFor(() => expect(wrapper.findComponent({ name: 'AccountMeView' }).exists()).toBe(true), {
      timeout: 2000,
      interval: 25,
    })

    expect(wrapper.findComponent({ name: 'AccountNotificationsView' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('switches to the requested tab straight from the route param, e.g. sessions', async () => {
    const router = mountAt('/account/sessions')
    await router.isReady()

    const wrapper = mountWithApp(AccountView, { global: { plugins: [router] } })

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'AccountSessionsView' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    expect(wrapper.findComponent({ name: 'AccountMeView' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('falls back to the me tab for an unknown :tab route param', async () => {
    const router = mountAt('/account/not-a-real-tab')
    await router.isReady()

    const wrapper = mountWithApp(AccountView, { global: { plugins: [router] } })

    await vi.waitFor(() => expect(wrapper.findComponent({ name: 'AccountMeView' }).exists()).toBe(true), {
      timeout: 2000,
      interval: 25,
    })

    wrapper.unmount()
  })
})
