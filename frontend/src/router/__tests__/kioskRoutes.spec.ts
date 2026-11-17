import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const refreshMock = vi.fn<() => Promise<void>>()
const userState: { user: { id: number } | null; sessionChecked: boolean } = {
  user: null,
  sessionChecked: false,
}

vi.mock('@/core/stores/currentUserStore', () => ({
  useCurrentUserStore: () => ({
    get user() {
      return userState.user
    },
    get loading() {
      return false
    },
    get sessionChecked() {
      return userState.sessionChecked
    },
    get isAdmin() {
      return false
    },
    refresh: refreshMock,
  }),
}))

const hostFetchMock = vi.fn<() => Promise<void>>()

vi.mock('@/core/host/stores/hostStore', () => ({
  useHostStore: () => ({
    fetch: hostFetchMock,
    get productionPlanningEnabled() {
      return true
    },
  }),
}))

vi.mock('@/features/auth/views/LoginView.vue', () => ({
  default: { name: 'LoginView', template: '<div />' },
}))

vi.mock('@/features/infoscreens/runtime/views/InfoscreenEntryView.vue', () => ({
  default: { name: 'InfoscreenEntryView', template: '<div />' },
}))

vi.mock('@/features/infoscreens/runtime/views/InfoscreenRegisterView.vue', () => ({
  default: { name: 'InfoscreenRegisterView', template: '<div />' },
}))

vi.mock('@/features/infoscreens/runtime/views/InfoscreenPreviewView.vue', () => ({
  default: { name: 'InfoscreenPreviewView', template: '<div />' },
}))

import router from '@/router'

// A wall display opens /infoscreen without a web session and must stay
// there: no session probe, no host bootstrap and no redirect to the login
// page. The builder preview is a normal signed-in page.
describe('router, kiosk routes', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    // Park the singleton router on a URL no test pushes, so every push below
    // is a real navigation that runs the guard.
    userState.user = null
    userState.sessionChecked = true
    await router.replace({ name: 'Login', query: { spec: 'kiosk-reset' } })

    vi.clearAllMocks()
    userState.sessionChecked = false
    refreshMock.mockImplementation(async () => {
      userState.sessionChecked = true
      throw new Error('401')
    })
    hostFetchMock.mockResolvedValue(undefined)
  })

  it.each(['/infoscreen', '/infoscreen/register'])(
    'opens %s without a session probe or a login redirect',
    async (path) => {
      await router.push(path)

      expect(router.currentRoute.value.path).toBe(path)
      expect(router.currentRoute.value.meta.layout).toBe('kiosk')
      expect(refreshMock).not.toHaveBeenCalled()
      expect(hostFetchMock).not.toHaveBeenCalled()
    },
  )

  it('sends a signed-out visitor of the preview to the login page', async () => {
    await router.push('/infoscreen/preview/3')

    expect(refreshMock).toHaveBeenCalledOnce()
    expect(router.currentRoute.value.name).toBe('Login')
    expect(router.currentRoute.value.query.redirect).toBe('/infoscreen/preview/3')
  })

  it('opens the preview in the kiosk layout for a signed-in viewer', async () => {
    refreshMock.mockImplementation(async () => {
      userState.user = { id: 1 }
      userState.sessionChecked = true
    })

    await router.push('/infoscreen/preview/3')

    expect(router.currentRoute.value.name).toBe('InfoscreenPreview')
    expect(router.currentRoute.value.meta.layout).toBe('kiosk')
  })
})
