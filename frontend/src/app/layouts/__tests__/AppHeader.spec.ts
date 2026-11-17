import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import OpenVue from 'openvue/config'
import Tooltip from 'openvue/tooltip'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import type { NotificationResponse } from '@/features/notifications'

const getNotificationsMock = vi.fn<() => Promise<NotificationResponse[]>>()
const markNotificationReadMock = vi.fn<(id: number) => Promise<void>>()
const markAllNotificationsReadMock = vi.fn<() => Promise<void>>()

vi.mock('@/features/notifications/api/getNotifications', () => ({
  getNotifications: () => getNotificationsMock(),
}))
vi.mock('@/features/notifications/api/markNotificationRead', () => ({
  markNotificationRead: (id: number) => markNotificationReadMock(id),
}))
vi.mock('@/features/notifications/api/markAllNotificationsRead', () => ({
  markAllNotificationsRead: () => markAllNotificationsReadMock(),
}))

import AppHeader from '../AppHeader.vue'

// A factory, not a shared constant: the store mutates `is_read` in place on
// whatever the mock resolves with (`markRead`'s real, unmocked logic), so a
// single shared object would leak that mutation from one test into the next.
function makeNotifications(): NotificationResponse[] {
  return [
    {
      id: 1,
      public_id: '11111111-1111-1111-1111-111111111111',
      type: 'demand',
      title: 'A',
      message: 'msg',
      is_read: false,
      created_at: '2026-08-20T10:00:00Z',
      demand_item_id: null,
      order_id: null,
      project_id: null,
      product_id: null,
      meeting_id: null,
    },
  ]
}

async function mountHeader() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
  await router.push('/')
  await router.isReady()

  const wrapper = mount(AppHeader, {
    props: { sidebarCollapsed: false },
    global: {
      plugins: [router, [OpenVue, { theme: { preset: Aura } }], i18n],
      directives: { tooltip: Tooltip },
    },
    attachTo: document.body,
  })
  await flushPromises()

  return wrapper
}

async function mountOpenHeader() {
  const wrapper = await mountHeader()

  // NotificationPanel only renders inside the account drawer.
  await wrapper.find('.avatar-button').trigger('click')
  await flushPromises()

  return wrapper
}

function setBranding(overrides: { app_description?: string | null; has_logo?: boolean } = {}) {
  usePublicBrandingStore().branding = {
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

// NotificationPanel does not own notificationsStore itself: AppHeader does,
// and passes it through as props/emits. These specs prove that wiring works
// end to end from AppHeader, not just that the panel's own prop/emit contract
// works in isolation (NotificationPanel.spec.ts covers that half).
describe('AppHeader, NotificationPanel wiring', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getNotificationsMock.mockImplementation(() => Promise.resolve(makeNotifications()))
    markNotificationReadMock.mockResolvedValue(undefined)
    markAllNotificationsReadMock.mockResolvedValue(undefined)
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('passes the store notifications and loading state through as props', async () => {
    const wrapper = await mountOpenHeader()

    const panel = wrapper.findComponent({ name: 'NotificationPanel' })
    expect(panel.exists()).toBe(true)
    expect(panel.props('items')).toEqual(makeNotifications())
    expect(panel.props('loading')).toBe(false)

    wrapper.unmount()
  })

  it('forwards mark-read and mark-all-read up through the store', async () => {
    const wrapper = await mountOpenHeader()
    const panel = wrapper.findComponent({ name: 'NotificationPanel' })

    panel.vm.$emit('mark-read', 1)
    await flushPromises()
    expect(markNotificationReadMock).toHaveBeenCalledWith(1)

    panel.vm.$emit('mark-all-read')
    await flushPromises()
    expect(markAllNotificationsReadMock).toHaveBeenCalledOnce()

    wrapper.unmount()
  })

  it('reflects the store unread count in the header badge', async () => {
    const wrapper = await mountOpenHeader()
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent({ name: 'OverlayBadge' }).props('value')).toBe('1')

    wrapper.unmount()
  })
})

// The countdown next to the avatar button is this account's only
// client-side warning that its session hard-expires: it must stay absent
// for every other account, and only tint red once under a minute remains.
describe('AppHeader, session countdown', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getNotificationsMock.mockImplementation(() => Promise.resolve([]))
    markNotificationReadMock.mockResolvedValue(undefined)
    markAllNotificationsReadMock.mockResolvedValue(undefined)
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renders no countdown when the store has no session expiry', async () => {
    const wrapper = await mountOpenHeader()

    expect(wrapper.find('.session-countdown').exists()).toBe(false)

    wrapper.unmount()
  })

  it('renders the countdown once the store has a session expiry', async () => {
    useCurrentUserStore().sessionExpiresAt = Date.now() + 5 * 60_000 + 30_000 // 5:30

    const wrapper = await mountOpenHeader()
    const countdown = wrapper.find('.session-countdown')

    expect(countdown.exists()).toBe(true)
    expect(countdown.text()).toBe('5:30')
    expect(countdown.classes()).not.toContain('warning')

    wrapper.unmount()
  })

  it('applies the warning class once under a minute remains', async () => {
    useCurrentUserStore().sessionExpiresAt = Date.now() + 45_000 // 0:45

    const wrapper = await mountOpenHeader()
    const countdown = wrapper.find('.session-countdown')

    expect(countdown.exists()).toBe(true)
    expect(countdown.classes()).toContain('warning')

    wrapper.unmount()
  })
})

// The branding tab's "Description" is a tagline under the app name in the
// header, and only there. It must vanish completely (no empty row shifting
// the wordmark) when unset, and stay put when a logo replaces the wordmark.
describe('AppHeader, branding description', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getNotificationsMock.mockImplementation(() => Promise.resolve([]))
    markNotificationReadMock.mockResolvedValue(undefined)
    markAllNotificationsReadMock.mockResolvedValue(undefined)
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renders only the wordmark when no description is set', async () => {
    setBranding({ app_description: null })

    const wrapper = await mountHeader()

    expect(wrapper.find('.brand').text()).toBe('Glados')
    expect(wrapper.find('.brand-description').exists()).toBe(false)
    expect(wrapper.find('.brand-block').classes()).not.toContain('has-description')

    wrapper.unmount()
  })

  it('renders the description under the app name once set', async () => {
    setBranding({ app_description: 'Production planning' })

    const wrapper = await mountHeader()
    const block = wrapper.find('.brand-block')

    expect(block.classes()).toContain('has-description')
    expect(block.find('.brand').text()).toBe('Glados')
    expect(block.find('.brand-description').text()).toBe('Production planning')

    wrapper.unmount()
  })

  it('keeps the description when a logo replaces the wordmark', async () => {
    setBranding({ app_description: 'Production planning', has_logo: true })

    const wrapper = await mountHeader()
    const block = wrapper.find('.brand-block')

    expect(block.find('.brand-logo').exists()).toBe(true)
    expect(block.find('.brand').exists()).toBe(false)
    expect(block.find('.brand-description').text()).toBe('Production planning')

    wrapper.unmount()
  })
})
