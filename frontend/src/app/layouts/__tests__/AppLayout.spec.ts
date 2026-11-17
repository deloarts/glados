import { describe, it, expect, vi, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

import AppLayout from '../AppLayout.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { useScan } from '@/features/scan'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useAnnouncementsStore } from '@/features/announcements'

// ScanDialog pulls in qr-scanner; stub it so letting the dialog actually
// mount in this spec doesn't reach for camera APIs jsdom doesn't have.
vi.mock('qr-scanner', () => ({
  default: class {
    static hasCamera(): Promise<boolean> {
      return Promise.resolve(false)
    }
    start(): Promise<void> {
      return Promise.resolve()
    }
    stop(): void {}
    destroy(): void {}
  },
}))

// The LotDetailDialog stub below replaces the rendered component, but the
// async wrapper still runs its loader, and the real module pulls in most
// other features. On a slow runner that import graph is still loading when
// the environment is torn down, so the loader gets a stand-in module.
vi.mock('@/features/production/lots/components/LotDetailDialog.vue', () => ({
  default: { name: 'LotDetailDialog', render: () => null },
}))

async function mountLayout() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
  await router.push('/')
  await router.isReady()

  return mountWithApp(AppLayout, {
    pinia,
    global: {
      plugins: [router],
      stubs: {
        // Out of scope for this spec: AppSidebar/AppHeader/AppFooter and the
        // (already-async) LotDetailDialog have their own heavy dependency
        // trees unrelated to what's being verified here.
        AppSidebar: true,
        AppHeader: true,
        AppFooter: true,
        LotDetailDialog: true,
        RouterView: true,
      },
    },
  })
}

describe('AppLayout, ScanDialog lazy loading', () => {
  afterEach(() => {
    useScan().closeScan()
  })

  it('does not mount ScanDialog synchronously', async () => {
    const wrapper = await mountLayout()

    expect(wrapper.findComponent({ name: 'ScanDialog' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('resolves ScanDialog once the chunk loads, and round-trips v-model:visible', async () => {
    const wrapper = await mountLayout()
    // The dynamic import needs real macrotasks to resolve (module transform,
    // not just a microtask), so poll instead of a fixed wait: fast on the
    // happy path, tolerant under CI load.
    await vi.waitFor(() => expect(wrapper.findComponent({ name: 'ScanDialog' }).exists()).toBe(true), {
      timeout: 2000,
      interval: 25,
    })
    await flushPromises()

    const scanDialog = wrapper.findComponent({ name: 'ScanDialog' })
    expect(scanDialog.props('visible')).toBe(false)

    useScan().openScan()
    await flushPromises()
    expect(scanDialog.props('visible')).toBe(true)

    scanDialog.vm.$emit('update:visible', false)
    await flushPromises()
    expect(useScan().visible.value).toBe(false)

    wrapper.unmount()
  })
})

// MaintenanceBanner.vue sits between the header and .shell-body as a plain
// sibling (see AppLayout.vue's template); it must stay that way, since
// .shell-body's flex: 1; min-height: 0 is what gives it the remaining
// height, and nesting the banner inside would shrink that available space
// or (worse) get clipped by .shell-body's scroll container instead of
// pushing it down.
describe('AppLayout, maintenance banner placement', () => {
  it('renders nothing extra when maintenance is off', async () => {
    const wrapper = await mountLayout()

    expect(wrapper.find('.maintenance-banner').exists()).toBe(false)

    wrapper.unmount()
  })

  it('renders the banner as a sibling of .shell-body, before it, not nested inside it', async () => {
    const wrapper = await mountLayout()
    useHostStore().maintenanceEnabled = true
    await flushPromises()

    const shellBody = wrapper.find('.shell-body')
    expect(shellBody.exists()).toBe(true)
    // Not inside .shell-body: the shell body is unaffected by the banner's
    // presence.
    expect(shellBody.find('.maintenance-banner').exists()).toBe(false)

    const shell = wrapper.find('.app-shell')
    const children = Array.from(shell.element.children)
    const bannerIndex = children.findIndex((el) => el.classList.contains('maintenance-banner'))
    const bodyIndex = children.findIndex((el) => el.classList.contains('shell-body'))
    expect(bannerIndex).toBeGreaterThanOrEqual(0)
    expect(bannerIndex).toBeLessThan(bodyIndex)

    wrapper.unmount()
  })
})

// AnnouncementBanner.vue sits ABOVE .shell-header (unlike MaintenanceBanner,
// which sits between the header and .shell-body); see AnnouncementBanner.vue's
// own comment for why: an admin-authored "we upgrade at 18:00" banner is
// meant to be the very first thing a signed-in user sees.
describe('AppLayout, announcement banner placement', () => {
  it('renders nothing extra when there is no banner', async () => {
    const wrapper = await mountLayout()

    expect(wrapper.find('.announcement-banner').exists()).toBe(false)

    wrapper.unmount()
  })

  it('renders the announcement banner as the first child of .app-shell, above the header', async () => {
    const wrapper = await mountLayout()
    useAnnouncementsStore().banner = {
      text: 'Upgrade tonight at 18:00.',
      severity: 'info',
      shows_from: null,
      shows_until: null,
      dismissable: true,
      updated_at: '2026-01-01T00:00:00Z',
    }
    await flushPromises()

    const shell = wrapper.find('.app-shell')
    const children = Array.from(shell.element.children)
    const bannerIndex = children.findIndex((el) => el.classList.contains('announcement-banner'))
    const headerIndex = children.findIndex((el) => el.classList.contains('shell-header'))
    expect(bannerIndex).toBeGreaterThanOrEqual(0)
    expect(bannerIndex).toBeLessThan(headerIndex)
    expect(wrapper.text()).toContain('Upgrade tonight at 18:00.')

    wrapper.unmount()
  })
})

describe('AppLayout, skip link', () => {
  it('renders a skip link as the first element of the shell, targeting the main content', async () => {
    const wrapper = await mountLayout()

    const shell = wrapper.find('.app-shell')
    expect(shell.element.firstElementChild?.classList.contains('skip-link')).toBe(true)

    const link = wrapper.find('.skip-link')
    expect(link.element.tagName).toBe('A')
    expect(link.attributes('href')).toBe('#main-content')
    expect(link.text()).toBe('Skip to main content')
  })

  it('targets a main element that can actually receive focus', async () => {
    const wrapper = await mountLayout()

    const main = wrapper.find('#main-content')
    expect(main.exists()).toBe(true)
    expect(main.element.tagName).toBe('MAIN')
    // tabindex="-1" makes an element focusable via script/anchor navigation
    // without adding it to the normal tab order.
    expect(main.attributes('tabindex')).toBe('-1')
  })

  // Only the scoped .skip-link CSS moves the link off-screen until it is
  // focused; nothing here hides it from assistive tech or pulls it out of
  // the tab order, which would defeat the point of a skip link entirely.
  it('stays keyboard-focusable and in the tab order, relying only on CSS to hide it visually', async () => {
    const wrapper = await mountLayout()

    const link = wrapper.find('.skip-link')
    expect(link.attributes('tabindex')).toBeUndefined()
    expect(link.attributes('aria-hidden')).toBeUndefined()
    expect(link.attributes('hidden')).toBeUndefined()
  })
})

describe('AppLayout, acknowledgement dialog', () => {
  it('mounts AcknowledgementDialog alongside SystemUserWarningDialog', async () => {
    const wrapper = await mountLayout()

    expect(wrapper.findComponent({ name: 'AcknowledgementDialog' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'SystemUserWarningDialog' }).exists()).toBe(true)

    wrapper.unmount()
  })
})
