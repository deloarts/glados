import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'


const pushMock = vi.fn<(...args: unknown[]) => void>()
const loginMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()

// Mutable so each test can set a different `redirect` query value before
// mounting: vi.mock factories are hoisted, so this can't be a per-test
// local without living on a module-scope object like this.
const routeQuery: Record<string, unknown> = {}

// Same story for the signed-in user postLoginTarget reads: a getter on the
// mock keeps every useCurrentUserStore() call (a fresh object each time)
// pointed at this one mutable box, so a test can flip it before mounting.
const currentUser: { value: { is_systemuser?: boolean; start_page?: string } | null } = {
  value: null,
}

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ query: routeQuery }),
}))

vi.mock('@/core/stores/currentUserStore', () => ({
  useCurrentUserStore: () => ({
    refresh: vi.fn<() => Promise<void>>(),
    get user() {
      return currentUser.value
    },
  }),
}))

vi.mock('@/features/auth/api/login', () => ({
  login: (...a: unknown[]) => loginMock(...a),
  verifyTotp: vi.fn<() => Promise<unknown>>(),
}))

vi.mock('@/features/auth/api/totp', () => ({
  enrollTotpWithSetupToken: vi.fn<() => Promise<unknown>>(),
  confirmTotpWithSetupToken: vi.fn<() => Promise<unknown>>(),
}))

import LoginView from '../LoginView.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

function mountLogin() {
  return mountWithApp(LoginView)
}

async function submitCredentials(wrapper: ReturnType<typeof mountLogin>) {
  await wrapper.find('#login-username').setValue('tester')
  // An empty password never submits (see LoginView's canSubmit guard), so
  // every one of these redirect scenarios needs a real one to reach login().
  await wrapper.find('input[type="password"]').setValue('secret')
  await wrapper.find('form').trigger('submit.prevent')
  await flushPromises()
}

// The router guard bounces an unauthenticated visit back here with
// ?redirect=<original path>, and a successful login pushes straight to it.
// That query value is attacker-controlled input the moment it's read off
// the URL, so every shape here must resolve to an internal path only.
//
// An unsafe/absent redirect does not fall back to the bare "/": it
// resolves the signed-in user's start-page preference (postLoginTarget's
// resolveStartPageRoute), falling back further to "/dashboard" when there is
// none. The mocked user objects below carry no `start_page`, so every case
// here lands on that final "/dashboard" fallback.
describe('LoginView, post-login redirect', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    for (const key of Object.keys(routeQuery)) delete routeQuery[key]
    currentUser.value = null
    loginMock.mockResolvedValue({ access_token: 'tok', token_type: 'bearer' })
  })

  it('navigates to an ordinary internal redirect path', async () => {
    routeQuery.redirect = '/production/lots'
    const wrapper = mountLogin()
    await submitCredentials(wrapper)

    expect(pushMock).toHaveBeenCalledWith('/production/lots')
  })

  it('falls back to the dashboard for a protocol-relative redirect (//evil.example)', async () => {
    routeQuery.redirect = '//evil.example'
    const wrapper = mountLogin()
    await submitCredentials(wrapper)

    expect(pushMock).toHaveBeenCalledWith('/dashboard')
  })

  it('falls back to the dashboard for a backslash redirect (browsers treat \\ as / )', async () => {
    routeQuery.redirect = '/\\evil.example'
    const wrapper = mountLogin()
    await submitCredentials(wrapper)

    expect(pushMock).toHaveBeenCalledWith('/dashboard')
  })

  it('falls back to the dashboard for an absolute external URL', async () => {
    routeQuery.redirect = 'https://evil.example'
    const wrapper = mountLogin()
    await submitCredentials(wrapper)

    expect(pushMock).toHaveBeenCalledWith('/dashboard')
  })

  it('falls back to the dashboard when there is no redirect param', async () => {
    const wrapper = mountLogin()
    await submitCredentials(wrapper)

    expect(pushMock).toHaveBeenCalledWith('/dashboard')
  })

  it("honors the user's start_page preference when there is no redirect param", async () => {
    currentUser.value = { is_systemuser: false, start_page: 'todo' }
    const wrapper = mountLogin()
    await submitCredentials(wrapper)

    expect(pushMock).toHaveBeenCalledWith('/todo')
  })

  it('prefers an explicit safe redirect over the start-page preference', async () => {
    currentUser.value = { is_systemuser: false, start_page: 'todo' }
    routeQuery.redirect = '/production/lots'
    const wrapper = mountLogin()
    await submitCredentials(wrapper)

    expect(pushMock).toHaveBeenCalledWith('/production/lots')
  })

  it('sends the system user to settings even with a redirect param', async () => {
    currentUser.value = { is_systemuser: true }
    routeQuery.redirect = '/production/lots'
    const wrapper = mountLogin()
    await submitCredentials(wrapper)

    expect(pushMock).toHaveBeenCalledWith('/settings')
  })

  it('sends the system user to settings with no redirect param', async () => {
    currentUser.value = { is_systemuser: true }
    const wrapper = mountLogin()
    await submitCredentials(wrapper)

    expect(pushMock).toHaveBeenCalledWith('/settings')
  })
})
