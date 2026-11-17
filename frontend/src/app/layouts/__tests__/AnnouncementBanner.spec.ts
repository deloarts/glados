import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useAnnouncementsStore } from '@/features/announcements'
import type { AnnouncementBanner as AnnouncementBannerData } from '@/features/announcements'
import type { AnnouncementSeverity } from '@/features/announcements'

import AnnouncementBanner from '../AnnouncementBanner.vue'

function makeBanner(overrides: Partial<AnnouncementBannerData> = {}): AnnouncementBannerData {
  return {
    text: 'We upgrade at 18:00.',
    severity: 'info',
    shows_from: null,
    shows_until: null,
    dismissable: true,
    updated_at: '2026-08-27T10:00:00Z',
    ...overrides,
  }
}

function mountBanner() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(AnnouncementBanner, { pinia })
  return { wrapper, store: useAnnouncementsStore() }
}

describe('AnnouncementBanner', () => {
  it('renders nothing when there is no banner', () => {
    const { wrapper } = mountBanner()

    expect(wrapper.find('[data-testid="announcement-banner"]').exists()).toBe(false)
  })

  it('shows the banner text verbatim (untranslated, pre-line)', async () => {
    const { wrapper, store } = mountBanner()
    store.banner = makeBanner({ text: 'We upgrade at 18:00.\nExpect a short outage.' })
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="announcement-banner"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('We upgrade at 18:00.')
    expect(wrapper.text()).toContain('Expect a short outage.')
  })

  it.each<[AnnouncementSeverity, string]>([
    ['info', 'info'],
    ['warning', 'warn'],
    ['danger', 'error'],
  ])('maps wire severity %s to OpenVue severity %s', async (wire, primeSeverity) => {
    const { wrapper, store } = mountBanner()
    store.banner = makeBanner({ severity: wire })
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent({ name: 'Message' }).props('severity')).toBe(primeSeverity)
  })

  it.each<[AnnouncementSeverity, string]>([
    ['info', 'mdi mdi-information-outline'],
    ['warning', 'mdi mdi-alert-outline'],
    ['danger', 'mdi mdi-alert-octagon-outline'],
  ])('shows a %s icon so colour is not the only severity cue', async (wire, icon) => {
    const { wrapper, store } = mountBanner()
    store.banner = makeBanner({ severity: wire })
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent({ name: 'Message' }).props('icon')).toBe(icon)
    expect(wrapper.find('[data-testid="announcement-banner-icon"]').classes()).toEqual(
      expect.arrayContaining(icon.split(' ')),
    )
  })

  it('offers no close button when the admin made the banner non-dismissable', async () => {
    const { wrapper, store } = mountBanner()
    store.banner = makeBanner({ dismissable: false })
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent({ name: 'Message' }).props('closable')).toBe(false)
    expect(wrapper.find('[data-testid="announcement-banner-close"]').exists()).toBe(false)
  })

  it('dismissing the banner (closing the Message) hides it', async () => {
    const { wrapper, store } = mountBanner()
    store.banner = makeBanner({ updated_at: 'v1' })
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="announcement-banner"]').exists()).toBe(true)

    await wrapper.findComponent({ name: 'Message' }).vm.$emit('close')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="announcement-banner"]').exists()).toBe(false)
  })

  it('the dismissal persists by updated_at - remounting with the same store still hides it', async () => {
    const { wrapper, store } = mountBanner()
    store.banner = makeBanner({ updated_at: 'v1' })
    await wrapper.vm.$nextTick()
    store.dismissBanner()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="announcement-banner"]').exists()).toBe(false)

    // A later refresh returning the *same* updated_at (nothing changed
    // server-side) must not un-dismiss it.
    store.banner = makeBanner({ updated_at: 'v1' })
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="announcement-banner"]').exists()).toBe(false)
  })

  it('an edited banner (a new updated_at) reappears even though the old one was dismissed', async () => {
    const { wrapper, store } = mountBanner()
    store.banner = makeBanner({ updated_at: 'v1' })
    await wrapper.vm.$nextTick()
    store.dismissBanner()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="announcement-banner"]').exists()).toBe(false)

    store.banner = makeBanner({ text: 'Edited message.', updated_at: 'v2' })
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="announcement-banner"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Edited message.')
  })
})
