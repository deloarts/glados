import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'

// LoginView pulls in authStore -> currentUserStore -> '@/core/api', whose
// module-level axios.create(...) call would otherwise throw against a bare
// mock (see currentUserStore.spec.ts, which mocks axios the same way for
// the same reason). publicBrandingStore talks to axios directly (it must
// work pre-auth), which is why the top-level `get` is mocked separately
// from the `instance` the api client instances get from `create()`.
const axiosGetMock = vi.fn<(url: string) => Promise<{ data: unknown }>>()

vi.mock('axios', () => {
  const instance = {
    get: vi.fn<() => void>(),
    post: vi.fn<() => void>(),
    put: vi.fn<() => void>(),
    delete: vi.fn<() => void>(),
    interceptors: {
      request: { use: vi.fn<() => void>() },
      response: { use: vi.fn<() => void>() },
    },
    // '@/core/api' and '@/core/api/auth' both set a default CSRF header
    // straight on the created instance (no interceptor involved).
    defaults: { headers: { common: {} } },
  }
  return {
    default: {
      get: (url: string) => axiosGetMock(url),
      create: () => instance,
      isAxiosError: () => false,
      isCancel: () => false,
    },
  }
})

const pushMock = vi.fn<(...args: unknown[]) => void>()

// currentUserStore imports the app's real router singleton to call
// router.push() from teardown helpers. This test drives its own throwaway
// router instance for useRoute()/useRouter() instead (see below), so the
// two must not be confused with one another.
vi.mock('@/router', () => ({
  default: {
    push: (...args: unknown[]) => pushMock(...args),
    currentRoute: { value: { name: 'Login', fullPath: '/login' } },
  },
}))

import LoginView from '../LoginView.vue'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'

function brandingResponse(
  overrides: Partial<{ maintenance_enabled: boolean; maintenance_message: string | null }> = {},
) {
  return {
    app_name: 'Glados',
    app_description: null,
    footer_text: null,
    company_name: null,
    contact_email: null,
    support_url: null,
    imprint_url: null,
    privacy_url: null,
    has_logo: false,
    has_favicon: false,
    has_login_background_video: false,
    default_language: 'enGB' as const,
    maintenance_enabled: false,
    maintenance_message: null,
    ...overrides,
  }
}

async function mountLoginView(query: Record<string, string> = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/login', name: 'Login', component: { template: '<div />' } }],
  })
  const search = new URLSearchParams(query).toString()
  await router.push(`/login${search ? `?${search}` : ''}`)
  await router.isReady()

  const wrapper = mount(LoginView, {
    global: {
      plugins: [router, [OpenVue, { theme: { preset: Aura } }], ToastService, i18n],
    },
  })
  await flushPromises()
  return wrapper
}

describe('LoginView, maintenance mode', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    // The real fetch() this triggers on mount (onMounted -> a plain GET) is
    // irrelevant here: branding is seeded directly below, and fetch()
    // swallows its own errors, so a rejected/unmocked call never clobbers
    // the seeded value.
    axiosGetMock.mockRejectedValue(new Error('not used in this spec'))
  })

  it('shows the banner with the admin-configured message when maintenance is on', async () => {
    usePublicBrandingStore().branding = brandingResponse({
      maintenance_enabled: true,
      maintenance_message: 'Upgrading the database, back shortly.',
    })

    const wrapper = await mountLoginView()

    expect(wrapper.text()).toContain('Upgrading the database, back shortly.')
    expect(wrapper.find('[data-testid="login-maintenance-banner"]').exists()).toBe(true)
  })

  it('falls back to the default message when the admin left it blank', async () => {
    usePublicBrandingStore().branding = brandingResponse({
      maintenance_enabled: true,
      maintenance_message: null,
    })

    const wrapper = await mountLoginView()

    expect(wrapper.text()).toContain(
      i18n.global.t('login.maintenance.defaultMessage') as string,
    )
  })

  it('shows nothing extra when maintenance is off', async () => {
    usePublicBrandingStore().branding = brandingResponse({ maintenance_enabled: false })

    const wrapper = await mountLoginView()

    expect(wrapper.find('[data-testid="login-maintenance-banner"]').exists()).toBe(false)
  })

  it('shows the maintenance-lockout notice when bounced here with reason=maintenance', async () => {
    usePublicBrandingStore().branding = brandingResponse()

    const wrapper = await mountLoginView({ reason: 'maintenance' })

    expect(wrapper.text()).toContain(
      i18n.global.t('login.errors.maintenanceLockout') as string,
    )
  })
})
