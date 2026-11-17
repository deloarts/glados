import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const refreshMock = vi.fn<() => Promise<void>>()
const userState: {
  user: { id: number; start_page?: string; is_systemuser?: boolean } | null
  loading: boolean
  // The session lives in an httponly cookie invisible to this script, see
  // currentUserStore's own comment on sessionChecked: true once refresh()
  // has settled once this app load, gating the guard's probe to "at most
  // once" per app load.
  sessionChecked: boolean
} = {
  user: null,
  loading: false,
  sessionChecked: false,
}

let isAdmin = false

vi.mock('@/core/stores/currentUserStore', () => ({
  useCurrentUserStore: () => ({
    get user() {
      return userState.user
    },
    get loading() {
      return userState.loading
    },
    get sessionChecked() {
      return userState.sessionChecked
    },
    get isAdmin() {
      return isAdmin
    },
    refresh: refreshMock,
  }),
}))

const hostFetchMock = vi.fn<() => Promise<void>>()
let productionPlanningEnabled = true
let todosEnabled: boolean | undefined
let calculationsEnabled: boolean | undefined

vi.mock('@/core/host/stores/hostStore', () => ({
  useHostStore: () => ({
    fetch: hostFetchMock,
    get productionPlanningEnabled() {
      return productionPlanningEnabled
    },
    get todosEnabled() {
      return todosEnabled
    },
    get calculationsEnabled() {
      return calculationsEnabled
    },
  }),
}))

vi.mock('@/features/auth/views/LoginView.vue', () => ({
  default: { name: 'LoginView', template: '<div />' },
}))

vi.mock('@/features/admin-settings/views/AdminSettingsView.vue', () => ({
  default: { name: 'AdminSettingsView', template: '<div />' },
}))

// The guard is under test, not the pages, but a navigation resolves its
// lazy route component before it settles. Loading the real dashboard pulls
// in its whole component tree and took seconds, enough to time the spec out
// when the suite runs in parallel.
vi.mock('@/features/dashboard/views/DashboardView.vue', () => ({
  default: { name: 'DashboardView', template: '<div />' },
}))

vi.mock('@/features/todo/views/TodoView.vue', () => ({
  default: { name: 'TodoView', template: '<div />' },
}))

import router from '@/router'

// Every test starts from the same "fresh app load" state: no user, no
// session check done yet, and refresh() defaulting to "no live session"
// (a test overrides this to simulate a successful probe). Declared at the
// file level so every describe block below inherits it without repeating
// the setup, and so a leftover mockImplementation from one test can never
// leak into the next.
//
// The router is a module singleton and keeps its location between tests,
// and pushing the location it is already on is a duplicated navigation that
// skips the guard. So each test first moves it to a login URL no test pushes
// (the query makes it unique), with the session already checked so the
// guard calls nothing on the way, and only then resets the session state.
beforeEach(async () => {
  setActivePinia(createPinia())
  userState.user = null
  userState.loading = false
  userState.sessionChecked = true
  await router.replace({ name: 'Login', query: { spec: 'reset' } })

  vi.clearAllMocks()
  userState.user = null
  userState.loading = false
  userState.sessionChecked = false
  refreshMock.mockReset()
  refreshMock.mockImplementation(async () => {
    userState.sessionChecked = true
  })
})

// The router guard validates the session and bootstraps the host store
// independently, so a transient /host/* failure never destroys a perfectly
// valid session: only a failed user refresh may leave the visitor
// unauthenticated, and host bootstrap is fire-and-forget.
describe('router auth guard, host bootstrap is decoupled from session validation', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    isAdmin = false
    productionPlanningEnabled = true
    hostFetchMock.mockResolvedValue(undefined)
  })

  it('redirects to Login when the initial session probe fails', async () => {
    refreshMock.mockImplementation(async () => {
      userState.sessionChecked = true
      throw new Error('401')
    })

    await router.push('/dashboard')

    expect(refreshMock).toHaveBeenCalledOnce()
    expect(router.currentRoute.value.name).toBe('Login')
  })

  it('does not let a host-bootstrap failure block a valid session', async () => {
    refreshMock.mockImplementation(async () => {
      userState.user = { id: 1 }
      userState.sessionChecked = true
    })
    hostFetchMock.mockRejectedValue(new Error('host unreachable'))

    await router.push('/dashboard')

    expect(router.currentRoute.value.name).toBe('Dashboard')
  })

  it('never calls the host bootstrap for an unauthenticated visitor', async () => {
    await router.push('/login')

    expect(hostFetchMock).not.toHaveBeenCalled()
  })

  it('fires the host bootstrap once authenticated', async () => {
    refreshMock.mockImplementation(async () => {
      userState.user = { id: 1 }
      userState.sessionChecked = true
    })

    await router.push('/dashboard')

    expect(hostFetchMock).toHaveBeenCalled()
  })
})

// /settings is the one route with a real access-control requirement
// (requiresAdmin); every other route is readable by any authenticated
// user (the Permission model only gates writes), so this is the only
// place route-level gating is meaningful.
describe('router auth guard, requiresAdmin', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    userState.user = { id: 1 }
    userState.sessionChecked = true
    hostFetchMock.mockResolvedValue(undefined)
  })

  it('redirects a non-admin away from /settings', async () => {
    isAdmin = false

    await router.push('/settings')

    expect(router.currentRoute.value.name).not.toBe('Settings')
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('lets an admin reach /settings', async () => {
    isAdmin = true

    await router.push('/settings')

    expect(router.currentRoute.value.name).toBe('Settings')
  })
})

// The `/` route has no `redirect` config (see the comment on it in
// src/router/index.ts): it is a real matched route the guard always
// redirects away from, once `isAuthenticated` reflects the freshly-loaded
// user, so a start-page preference is honored even on a cold reload rather
// than being resolved before `userStore.refresh()` has run.
describe('router auth guard, "/" resolves the signed-in user\'s start page', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    isAdmin = false
    productionPlanningEnabled = true
    hostFetchMock.mockResolvedValue(undefined)
  })

  it('sends an authenticated user with no start-page preference to the dashboard', async () => {
    userState.user = { id: 1 }
    userState.sessionChecked = true

    await router.push('/')

    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it("honors the user's start_page preference", async () => {
    userState.user = { id: 1, start_page: 'todo' }
    userState.sessionChecked = true

    await router.push('/')

    expect(router.currentRoute.value.path).toBe('/todo')
  })

  it('falls back to the dashboard for "production" when production planning is disabled', async () => {
    userState.user = { id: 1, start_page: 'production' }
    userState.sessionChecked = true
    productionPlanningEnabled = false

    await router.push('/')

    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('sends an unauthenticated visitor to Login instead of resolving a start page', async () => {
    await router.push('/')

    expect(router.currentRoute.value.name).toBe('Login')
  })
})

describe('router auth guard, switched-off modules', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    isAdmin = false
    productionPlanningEnabled = true
    todosEnabled = true
    calculationsEnabled = true
    hostFetchMock.mockResolvedValue(undefined)
    userState.user = { id: 1 }
    userState.sessionChecked = true
  })

  it('sends a page of a switched-off module to the dashboard', async () => {
    todosEnabled = false

    await router.push('/todo')

    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('falls back to the dashboard for the "todo" start page when todos are off', async () => {
    userState.user = { id: 1, start_page: 'todo' }
    todosEnabled = false

    await router.push('/')

    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('opens a tool without its saved calculation when calculations are off', async () => {
    calculationsEnabled = false

    await router.push('/tools/drive-sizing/123e4567-e89b-12d3-a456-426614174000')

    expect(router.currentRoute.value.path).toBe('/tools/drive-sizing')
  })
})
