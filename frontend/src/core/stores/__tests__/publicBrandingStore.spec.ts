import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createApp } from 'vue'

// This store talks to axios directly, not '@/core/api' (it must work
// pre-auth, before any token exists), so it's mocked here rather than via
// the usual '@/core/api' vi.mock used elsewhere. The mock must still satisfy
// axios.create(...).interceptors.*.use(...) though: currentUserStore.ts
// transitively imports '@/core/api', whose module-level `axios.create(...)`
// call would otherwise throw against a bare `{ get }` mock the moment this
// spec imports currentUserStore.
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

vi.mock('@/router', () => ({
  default: {
    push: (...args: unknown[]) => pushMock(...args),
    currentRoute: { value: { name: 'Dashboard', fullPath: '/dashboard' } },
  },
}))

import { usePublicBrandingStore } from '../publicBrandingStore'
import { useCurrentUserStore } from '../currentUserStore'
import { storeResetPlugin } from '../resetOnLogout'
import { i18n } from '@/core/i18n'
import { makeUserResponse } from '@/test-utils/factories'

function brandingResponse(
  overrides: Partial<{
    default_language: string
    app_description: string | null
    contact_email: string | null
    support_url: string | null
    imprint_url: string | null
    privacy_url: string | null
  }> = {},
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
    default_language: 'enGB',
    maintenance_enabled: false,
    maintenance_message: null,
    ...overrides,
  }
}

describe('publicBrandingStore, default_language race guard against currentUserStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    i18n.global.locale.value = 'enGB'
  })

  afterEach(() => {
    i18n.global.locale.value = 'enGB'
  })

  it('applies default_language to the pre-login screen when nobody is signed in', async () => {
    axiosGetMock.mockResolvedValue({ data: brandingResponse({ default_language: 'deAT' }) })

    await usePublicBrandingStore().fetch()

    expect(i18n.global.locale.value).toBe('deAT')
  })

  it('does not clobber a signed-in user’s own language preference', async () => {
    useCurrentUserStore().user = makeUserResponse({ language: 'enGB' })
    axiosGetMock.mockResolvedValue({ data: brandingResponse({ default_language: 'deAT' }) })

    await usePublicBrandingStore().fetch()

    // The signed-in user's own language (already applied by refresh()) must
    // survive branding's fetch() landing afterwards.
    expect(i18n.global.locale.value).toBe('enGB')
  })
})

// The header drops its whole tagline row on `null`, so the store has to
// normalise every "nothing to show" shape (never fetched, left blank in the
// branding tab, or whitespace via the API) to exactly that.
describe('publicBrandingStore, appDescription', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    i18n.global.locale.value = 'enGB'
  })

  afterEach(() => {
    i18n.global.locale.value = 'enGB'
  })

  it('is null before branding has been fetched', () => {
    expect(usePublicBrandingStore().appDescription).toBeNull()
  })

  it('is null when the branding tab left the description blank', async () => {
    axiosGetMock.mockResolvedValue({ data: brandingResponse({ app_description: null }) })

    await usePublicBrandingStore().fetch()

    expect(usePublicBrandingStore().appDescription).toBeNull()
  })

  it('normalises a whitespace-only description to null', async () => {
    axiosGetMock.mockResolvedValue({ data: brandingResponse({ app_description: '   ' }) })

    await usePublicBrandingStore().fetch()

    expect(usePublicBrandingStore().appDescription).toBeNull()
  })

  it('exposes the configured description', async () => {
    axiosGetMock.mockResolvedValue({
      data: brandingResponse({ app_description: 'Production planning' }),
    })

    await usePublicBrandingStore().fetch()

    expect(usePublicBrandingStore().appDescription).toBe('Production planning')
  })
})

// The footer renders these blindly as anchors in this order, so the store
// owns the shaping: drop the unset ones, turn the email into mailto:, and
// treat whitespace like unset.
describe('publicBrandingStore, footerLinks', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    i18n.global.locale.value = 'enGB'
  })

  afterEach(() => {
    i18n.global.locale.value = 'enGB'
  })

  it('is empty before branding has been fetched', () => {
    expect(usePublicBrandingStore().footerLinks).toEqual([])
  })

  it('is empty when none of the contact & legal fields are set', async () => {
    axiosGetMock.mockResolvedValue({ data: brandingResponse() })

    await usePublicBrandingStore().fetch()

    expect(usePublicBrandingStore().footerLinks).toEqual([])
  })

  it('lists the configured ones in display order, the email as mailto:', async () => {
    axiosGetMock.mockResolvedValue({
      data: brandingResponse({
        contact_email: 'office@example.com',
        support_url: 'https://example.com/support',
        imprint_url: 'https://example.com/imprint',
        privacy_url: 'https://example.com/privacy',
      }),
    })

    await usePublicBrandingStore().fetch()

    expect(usePublicBrandingStore().footerLinks).toEqual([
      { key: 'contact', href: 'mailto:office@example.com' },
      { key: 'support', href: 'https://example.com/support' },
      { key: 'imprint', href: 'https://example.com/imprint' },
      { key: 'privacy', href: 'https://example.com/privacy' },
    ])
  })

  it('skips unset and whitespace-only entries without disturbing the order', async () => {
    axiosGetMock.mockResolvedValue({
      data: brandingResponse({
        contact_email: '   ',
        support_url: null,
        imprint_url: 'https://example.com/imprint',
        privacy_url: 'https://example.com/privacy',
      }),
    })

    await usePublicBrandingStore().fetch()

    expect(usePublicBrandingStore().footerLinks).toEqual([
      { key: 'imprint', href: 'https://example.com/imprint' },
      { key: 'privacy', href: 'https://example.com/privacy' },
    ])
  })
})

// Mirrors the Maintenance tab's toggle/message, but pre-auth: the login
// screen has no token yet, so this (and hostStore's own copy for signed-in
// users) is the only way it can know to show the warning.
describe('publicBrandingStore, maintenanceEnabled / maintenanceMessage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('is false/null before branding has been fetched', () => {
    const store = usePublicBrandingStore()

    expect(store.maintenanceEnabled).toBe(false)
    expect(store.maintenanceMessage).toBeNull()
  })

  it('exposes enabled + the admin message once fetched', async () => {
    axiosGetMock.mockResolvedValue({
      data: {
        ...brandingResponse(),
        maintenance_enabled: true,
        maintenance_message: 'Upgrading the database, back shortly.',
      },
    })

    const store = usePublicBrandingStore()
    await store.fetch()

    expect(store.maintenanceEnabled).toBe(true)
    expect(store.maintenanceMessage).toBe('Upgrading the database, back shortly.')
  })

  it('is false/null when the tab has maintenance switched off', async () => {
    axiosGetMock.mockResolvedValue({
      data: { ...brandingResponse(), maintenance_enabled: false, maintenance_message: null },
    })

    const store = usePublicBrandingStore()
    await store.fetch()

    expect(store.maintenanceEnabled).toBe(false)
    expect(store.maintenanceMessage).toBeNull()
  })
})

// Exercised with storeResetPlugin actually installed (unlike the guard tests
// above) so this proves the read-before-reset ordering in
// currentUserStore.logout() for real: publicBranding is not in
// DEFAULT_EXCLUDED_STORE_IDS, so resetAllStores() wipes it back to null. If
// logout() read it even one line too late, this would regress to the
// 'enGB' fallback instead of the tenant's configured default.
describe('currentUserStore.logout(), resets the locale to the branding default', () => {
  beforeEach(() => {
    const pinia = createPinia()
    const app = createApp({})
    app.use(pinia)
    pinia.use(storeResetPlugin)
    setActivePinia(pinia)
    vi.clearAllMocks()
    i18n.global.locale.value = 'enGB'
  })

  afterEach(() => {
    i18n.global.locale.value = 'enGB'
  })

  it("resets i18n.global.locale to the branding store's default_language, not the departing user's own", async () => {
    axiosGetMock.mockResolvedValue({ data: brandingResponse({ default_language: 'deAT' }) })
    await usePublicBrandingStore().fetch()

    const currentUser = useCurrentUserStore()
    currentUser.user = makeUserResponse({ language: 'enGB' })
    // The signed-in user's own preference, as refresh() would have applied.
    i18n.global.locale.value = 'enGB'

    currentUser.logout()

    expect(i18n.global.locale.value).toBe('deAT')
  })

  it("falls back to 'enGB' on logout() when branding was never fetched", () => {
    const currentUser = useCurrentUserStore()
    currentUser.user = makeUserResponse()

    currentUser.logout()

    expect(i18n.global.locale.value).toBe('enGB')
  })

  // sessionExpired() is the other teardown path to the login page (token
  // rejected mid-session) and shares logout()'s reset. It must land the
  // user on a login page in the tenant's language just the same.
  it('sessionExpired() resets the locale the same way logout() does', async () => {
    axiosGetMock.mockResolvedValue({ data: brandingResponse({ default_language: 'deAT' }) })
    await usePublicBrandingStore().fetch()

    const currentUser = useCurrentUserStore()
    currentUser.user = makeUserResponse({ language: 'enGB' })
    i18n.global.locale.value = 'enGB'

    currentUser.sessionExpired()

    expect(i18n.global.locale.value).toBe('deAT')
  })
})
