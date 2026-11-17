import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { computed, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import {
  DEVICE_SCREEN_MEMORY_KEY,
  forgetShownScreenLanguage,
  paintRememberedScreenTheme,
  readDeviceScreenMemory,
  updateDeviceScreenMemory,
} from '@/core/terminal/deviceScreenMemory'
import { getDisplayTimezone, setDisplayTimezone } from '@/core/utils/dates'
import { makeTestRouter, RouteStub } from '@/test-utils/factories'
import { mountWithApp } from '@/test-utils/mountWithApp'
import type { TerminalDeviceState } from '@/core/terminal/terminalApi'

import type { InfoscreenRuntimePhase, SignInStep } from '../composables/useInfoscreenRuntime'
import type { InfoscreenFeedResponse, TerminalMessage } from '../types/infoscreenFeed'
import { displayZone } from '../utils/infoscreenFormat'
import { deviceStateFixture, feedFixture } from './infoscreenFixtures'

const phase = ref<InfoscreenRuntimePhase>('booting')
const deviceState = ref<TerminalDeviceState | null>(null)
const feed = ref<InfoscreenFeedResponse | null>(null)
const identifying = ref(false)
const signInStep = ref<SignInStep>({ id: 'bridge', state: 'running' })

vi.mock('../composables/useInfoscreenRuntime', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../composables/useInfoscreenRuntime')>()),
  useInfoscreenRuntime: () => ({
    phase: computed(() => phase.value),
    sessionError: computed(() => null),
    signInStep: computed(() => signInStep.value),
    attempt: ref(1),
    lastAttemptAt: ref(null),
    identity: ref(null),
    deviceState,
    feed,
    staleSince: ref(null),
    identifying,
    start: () => {},
    stop: () => {},
  }),
}))

const getInfoscreenPreviewFeed = vi.fn<(id: number) => Promise<InfoscreenFeedResponse>>()
vi.mock('../api/getInfoscreenPreviewFeed', () => ({
  getInfoscreenPreviewFeed: (id: number) => getInfoscreenPreviewFeed(id),
}))

vi.mock('@/core/realtime/useLiveRefresh', () => ({ useLiveRefresh: () => {} }))

import InfoscreenEntryView from '../views/InfoscreenEntryView.vue'
import InfoscreenPreviewView from '../views/InfoscreenPreviewView.vue'
import InfoscreenRegisterView from '../views/InfoscreenRegisterView.vue'

function messageFixture(overrides: Partial<TerminalMessage> = {}): TerminalMessage {
  return {
    id: 1,
    severity: 'warning',
    style: 'banner',
    show_until: '2026-10-30T08:15:00Z',
    text: '**Fire drill** at 10:00',
    ...overrides,
  }
}

// Fakes the timers and the clock but not setImmediate, which flushPromises needs.
function fakeClock(): void {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] })
  vi.setSystemTime(new Date('2026-10-30T08:00:00Z'))
}

function kioskRouter() {
  return makeTestRouter([
    { path: '/infoscreen', name: 'Infoscreen', component: RouteStub },
    { path: '/infoscreen/register', name: 'InfoscreenRegister', component: RouteStub },
    { path: '/infoscreen/preview/:id', name: 'InfoscreenPreview', component: RouteStub },
  ])
}

describe('infoscreen views', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    phase.value = 'booting'
    deviceState.value = null
    feed.value = null
    identifying.value = false
    signInStep.value = { id: 'bridge', state: 'running' }
    document.documentElement.classList.remove('p-dark')
    localStorage.clear()
    forgetShownScreenLanguage()
    i18n.global.locale.value = 'enGB'
  })

  afterEach(() => {
    vi.useRealTimers()
    i18n.global.locale.value = 'enGB'
  })

  it('moves a pending device to the register page', async () => {
    const router = kioskRouter()
    await router.push('/infoscreen')
    mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })

    phase.value = 'pending'
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('InfoscreenRegister')
  })

  it('shows the pairing code large on the register page', async () => {
    const router = kioskRouter()
    await router.push('/infoscreen/register')
    phase.value = 'pending'
    deviceState.value = deviceStateFixture({ status: 'pending', pairing_code: 'K7M3QX' })

    const wrapper = mountWithApp(InfoscreenRegisterView, { pinia, global: { plugins: [router] } })
    await flushPromises()

    const code = wrapper.get('[data-testid="pairing-code"]')
    expect(code.findAll('span')).toHaveLength(6)
    expect(code.attributes('aria-label')).toBe('K7M3QX')
    expect(wrapper.text()).toContain('Resources → Terminals → Approve')
    expect(wrapper.get('[data-testid="report-code"]').text()).toBe('PENDING_APPROVAL')
  })

  it('goes back to the entry page once the device is approved', async () => {
    const router = kioskRouter()
    await router.push('/infoscreen/register')
    phase.value = 'pending'
    mountWithApp(InfoscreenRegisterView, { pinia, global: { plugins: [router] } })

    phase.value = 'approved_unassigned'
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('Infoscreen')
  })

  it('shows the device name while no infoscreen is assigned', async () => {
    const router = kioskRouter()
    await router.push('/infoscreen')
    phase.value = 'approved_unassigned'
    signInStep.value = { id: 'infoscreen', state: 'waiting' }
    deviceState.value = deviceStateFixture({ infoscreen_id: null, name: 'Office Display' })

    const wrapper = mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })

    expect(wrapper.get('[data-testid="report-title"]').text()).toBe('Office Display')
    expect(wrapper.text()).toContain('no infoscreen is assigned to this display yet')
    expect(wrapper.get('[data-testid="report-step-infoscreen"]').attributes('data-state')).toBe('waiting')
  })

  it('tells a display without a bridge what it needs', async () => {
    const router = kioskRouter()
    await router.push('/infoscreen')
    phase.value = 'bridge_missing'
    signInStep.value = { id: 'bridge', state: 'failed' }

    const wrapper = mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })

    expect(wrapper.text()).toContain('Terminal service not answering')
    expect(wrapper.get('[data-testid="report-step-bridge"]').attributes('data-state')).toBe('failed')
    expect(wrapper.get('[data-testid="report-hint"]').text()).toContain('glados-terminal')
    expect(wrapper.get('[data-testid="report-status"]').text()).toContain('attempt 1')
  })

  it('shows the identify overlay with the device name', async () => {
    const router = kioskRouter()
    await router.push('/infoscreen')
    phase.value = 'showing'
    feed.value = feedFixture()
    deviceState.value = deviceStateFixture({ name: 'Hall 2 Display' })
    identifying.value = true

    const wrapper = mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })

    expect(wrapper.get('[data-testid="identify-overlay"]').text()).toContain('Hall 2 Display')
  })

  it('applies the screen theme on the device', async () => {
    const router = kioskRouter()
    await router.push('/infoscreen')
    const layoutStore = useLayoutStore()
    const applyPreset = vi.spyOn(layoutStore, 'applyPreset')
    phase.value = 'showing'
    feed.value = feedFixture()

    mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })
    await flushPromises()

    expect(applyPreset).toHaveBeenCalledWith('Nora', 'emerald')
    expect(layoutStore.isDarkMode).toBe(true)
  })

  it('shows booting and loading the infoscreen as one and the same view', async () => {
    const router = kioskRouter()
    await router.push('/infoscreen')
    const wrapper = mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })
    const booting = wrapper.get('[data-testid="sign-in-report"]').element

    phase.value = 'showing'
    signInStep.value = { id: 'infoscreen', state: 'running' }
    deviceState.value = deviceStateFixture()
    await flushPromises()

    const loading = wrapper.get('[data-testid="sign-in-report"]')
    expect(loading.element).toBe(booting)
    expect(loading.attributes('data-state')).toBe('starting')
    expect(wrapper.get('[data-testid="report-step-infoscreen"]').attributes('data-state')).toBe('running')

    feed.value = feedFixture()
    await flushPromises()
    expect(wrapper.find('[data-testid="sign-in-report"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="infoscreen-page"]').exists()).toBe(true)
  })

  it('shows the pairing code in the frame of the starting screen', async () => {
    const router = kioskRouter()
    await router.push('/infoscreen/register')
    phase.value = 'pending'
    signInStep.value = { id: 'approval', state: 'waiting' }
    deviceState.value = deviceStateFixture({ status: 'pending', pairing_code: 'K7M3QX' })

    const wrapper = mountWithApp(InfoscreenRegisterView, { pinia, global: { plugins: [router] } })
    await flushPromises()

    const report = wrapper.get('[data-testid="sign-in-report"]')
    expect(report.find('[data-testid="pairing-code"]').exists()).toBe(true)
    expect(report.get('[data-testid="report-step-approval"]').attributes('data-state')).toBe('waiting')
    // The pairing panel carries the approve hint instead of the check box.
    expect(report.find('[data-testid="report-hint"]').exists()).toBe(false)
  })

  it('remembers the screen theme, and the feed replaces a remembered one', async () => {
    updateDeviceScreenMemory({
      theme: { color_mode: 'light', theme_preset: 'Lara', primary_color: null },
    })
    const layoutStore = useLayoutStore()
    const applyPreset = vi.spyOn(layoutStore, 'applyPreset')
    expect(paintRememberedScreenTheme()).toBe(true)
    expect(applyPreset).toHaveBeenLastCalledWith('Lara', 'glados')
    expect(layoutStore.isDarkMode).toBe(false)

    const router = kioskRouter()
    await router.push('/infoscreen')
    phase.value = 'showing'
    feed.value = feedFixture()
    mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })
    await flushPromises()

    expect(applyPreset).toHaveBeenLastCalledWith('Nora', 'emerald')
    expect(layoutStore.isDarkMode).toBe(true)
    expect(readDeviceScreenMemory().theme).toEqual({
      color_mode: 'dark',
      theme_preset: 'Nora',
      primary_color: 'emerald',
    })
  })

  it('never remembers the theme of a preview', async () => {
    const router = kioskRouter()
    await router.push('/infoscreen/preview/3')
    getInfoscreenPreviewFeed.mockResolvedValue(feedFixture())

    const wrapper = mountWithApp(InfoscreenPreviewView, { pinia, global: { plugins: [router] } })
    await flushPromises()

    expect(localStorage.getItem(DEVICE_SCREEN_MEMORY_KEY)).toBeNull()
    wrapper.unmount()
  })

  it('previews a screen in its theme and gives the viewer theirs back on leave', async () => {
    const router = kioskRouter()
    await router.push('/infoscreen/preview/3')
    const layoutStore = useLayoutStore()
    layoutStore.setDarkMode(false)
    const applyPreset = vi.spyOn(layoutStore, 'applyPreset')
    getInfoscreenPreviewFeed.mockResolvedValue(feedFixture())

    const wrapper = mountWithApp(InfoscreenPreviewView, { pinia, global: { plugins: [router] } })
    await flushPromises()

    expect(getInfoscreenPreviewFeed).toHaveBeenCalledWith(3)
    expect(wrapper.find('[data-testid="infoscreen-page"]').exists()).toBe(true)
    expect(applyPreset).toHaveBeenLastCalledWith('Nora', 'emerald')
    expect(layoutStore.isDarkMode).toBe(true)

    wrapper.unmount()

    expect(applyPreset).toHaveBeenLastCalledWith('Aura', undefined)
    expect(layoutStore.isDarkMode).toBe(false)
  })

  it('previews in the tenant timezone the feed names, as the device does', async () => {
    const router = kioskRouter()
    await router.push('/infoscreen/preview/3')
    getInfoscreenPreviewFeed.mockResolvedValue(feedFixture({ timezone: 'Asia/Tokyo' }))

    const wrapper = mountWithApp(InfoscreenPreviewView, { pinia, global: { plugins: [router] } })
    await flushPromises()

    expect(getDisplayTimezone()).toBe('Asia/Tokyo')

    wrapper.unmount()
    setDisplayTimezone(null)
  })

  it('says so when the previewed screen does not exist', async () => {
    const router = kioskRouter()
    await router.push('/infoscreen/preview/99')
    const { AxiosError } = await import('axios')
    getInfoscreenPreviewFeed.mockRejectedValue(
      new AxiosError('x', 'ERR', undefined, undefined, {
        status: 404,
        data: {},
      } as never),
    )

    const wrapper = mountWithApp(InfoscreenPreviewView, { pinia, global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('This infoscreen does not exist.')
  })

  it('shows the location under the name on the identify overlay', async () => {
    const router = kioskRouter()
    await router.push('/infoscreen')
    phase.value = 'showing'
    feed.value = feedFixture()
    deviceState.value = deviceStateFixture({ name: 'Hall 2 Display', location: 'Hall 2, north wall' })
    identifying.value = true

    const wrapper = mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })

    const overlay = wrapper.get('[data-testid="identify-overlay"]')
    expect(overlay.text()).toContain('Hall 2 Display')
    expect(overlay.get('[data-testid="identify-overlay-location"]').text()).toBe('Hall 2, north wall')
  })

  it('leaves the location out of the identify overlay when none is set', async () => {
    const router = kioskRouter()
    await router.push('/infoscreen')
    deviceState.value = deviceStateFixture()
    identifying.value = true

    const wrapper = mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })

    expect(wrapper.find('[data-testid="identify-overlay-location"]').exists()).toBe(false)
  })

  describe('messages to terminals', () => {
    it('shows a message as a banner above the screen and hides it at its end without a refetch', async () => {
      fakeClock()
      const router = kioskRouter()
      await router.push('/infoscreen')
      phase.value = 'showing'
      feed.value = feedFixture()
      deviceState.value = deviceStateFixture({ broadcast: messageFixture() })

      const wrapper = mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })
      await flushPromises()

      const banner = wrapper.get('[data-testid="terminal-message-banner"]')
      expect(banner.attributes('data-severity')).toBe('warning')
      expect(banner.html()).toContain('<strong>Fire drill</strong>')
      expect(wrapper.find('[data-testid="infoscreen-page"]').exists()).toBe(true)
      expect(wrapper.find('[data-testid="terminal-message-fullscreen"]').exists()).toBe(false)

      vi.advanceTimersByTime(15 * 60 * 1000 - 1)
      await flushPromises()
      expect(wrapper.find('[data-testid="terminal-message-banner"]').exists()).toBe(true)

      vi.advanceTimersByTime(1)
      await flushPromises()
      expect(wrapper.find('[data-testid="terminal-message-banner"]').exists()).toBe(false)
      expect(wrapper.find('[data-testid="infoscreen-page"]').exists()).toBe(true)
    })

    it('shows a message over the whole display in the fullscreen style', async () => {
      fakeClock()
      const router = kioskRouter()
      await router.push('/infoscreen')
      phase.value = 'showing'
      feed.value = feedFixture()
      deviceState.value = deviceStateFixture({
        broadcast: messageFixture({ style: 'fullscreen', severity: 'danger', text: 'Evacuate hall 2' }),
      })

      const wrapper = mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })
      await flushPromises()

      const overlay = wrapper.get('[data-testid="terminal-message-fullscreen"]')
      expect(overlay.text()).toBe('Evacuate hall 2')
      expect(overlay.attributes('data-severity')).toBe('danger')
      expect(wrapper.find('[data-testid="terminal-message-banner"]').exists()).toBe(false)
    })

    it('shows nothing for a message whose end has passed', async () => {
      fakeClock()
      const router = kioskRouter()
      await router.push('/infoscreen')
      phase.value = 'showing'
      feed.value = feedFixture()
      deviceState.value = deviceStateFixture({
        broadcast: messageFixture({ show_until: '2026-10-30T07:59:00Z' }),
      })

      const wrapper = mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })
      await flushPromises()

      expect(wrapper.find('[data-testid="terminal-message-banner"]').exists()).toBe(false)
    })

    it('shows the message on the waiting screen of a display without an infoscreen', async () => {
      fakeClock()
      const router = kioskRouter()
      await router.push('/infoscreen')
      phase.value = 'approved_unassigned'
      signInStep.value = { id: 'infoscreen', state: 'waiting' }
      deviceState.value = deviceStateFixture({ infoscreen_id: null, broadcast: messageFixture() })

      const wrapper = mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })
      await flushPromises()

      expect(wrapper.find('[data-testid="sign-in-report"]').exists()).toBe(true)
      expect(wrapper.get('[data-testid="terminal-message-banner"]').text()).toContain('Fire drill')
    })

    it('follows a message that ends early or is replaced', async () => {
      fakeClock()
      const router = kioskRouter()
      await router.push('/infoscreen')
      phase.value = 'showing'
      feed.value = feedFixture()
      deviceState.value = deviceStateFixture({ broadcast: messageFixture() })
      const wrapper = mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })
      await flushPromises()

      deviceState.value = deviceStateFixture({ broadcast: messageFixture({ id: 2, text: 'Canteen closed' }) })
      await flushPromises()
      expect(wrapper.get('[data-testid="terminal-message-banner"]').text()).toBe('Canteen closed')

      deviceState.value = deviceStateFixture({ broadcast: null })
      await flushPromises()
      expect(wrapper.find('[data-testid="terminal-message-banner"]').exists()).toBe(false)
    })

    it('shows the message of the preview feed in the preview', async () => {
      fakeClock()
      const router = kioskRouter()
      await router.push('/infoscreen/preview/3')
      getInfoscreenPreviewFeed.mockResolvedValue(
        feedFixture({ broadcast: messageFixture({ style: 'fullscreen' }) }),
      )

      const wrapper = mountWithApp(InfoscreenPreviewView, { pinia, global: { plugins: [router] } })
      await flushPromises()

      expect(wrapper.get('[data-testid="terminal-message-fullscreen"]').text()).toContain('Fire drill')
      wrapper.unmount()
    })
  })

  describe('screen language', () => {
    it('switches the device to the language of the feed and remembers it', async () => {
      const router = kioskRouter()
      await router.push('/infoscreen')
      phase.value = 'showing'
      feed.value = feedFixture({ language: 'deAT' })

      mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })
      await flushPromises()

      expect(i18n.global.locale.value).toBe('deAT')
      expect(readDeviceScreenMemory().language).toBe('deAT')

      feed.value = feedFixture({ language: 'enGB' })
      await flushPromises()
      expect(i18n.global.locale.value).toBe('enGB')
      expect(readDeviceScreenMemory().language).toBe('enGB')
    })

    it('draws dates in the language of the screen', async () => {
      const router = kioskRouter()
      await router.push('/infoscreen')
      phase.value = 'showing'
      const base = feedFixture()
      feed.value = feedFixture({
        language: 'deAT',
        infoscreen: { ...base.infoscreen, header: { ...base.infoscreen.header, right: ['date'] } },
      })

      const wrapper = mountWithApp(InfoscreenEntryView, { pinia, global: { plugins: [router] } })
      await flushPromises()

      const weekday = new Intl.DateTimeFormat('de-AT', { weekday: 'long', timeZone: displayZone() }).format(
        new Date(),
      )
      expect(wrapper.get('[data-testid="bar-date"]').text()).toContain(weekday)
    })

    it('previews a screen in its language and gives the viewer theirs back on leave', async () => {
      const router = kioskRouter()
      await router.push('/infoscreen/preview/3')
      getInfoscreenPreviewFeed.mockResolvedValue(feedFixture({ language: 'deAT' }))

      const wrapper = mountWithApp(InfoscreenPreviewView, { pinia, global: { plugins: [router] } })
      await flushPromises()
      expect(i18n.global.locale.value).toBe('deAT')

      wrapper.unmount()

      expect(i18n.global.locale.value).toBe('enGB')
      expect(localStorage.getItem(DEVICE_SCREEN_MEMORY_KEY)).toBeNull()
    })

    it('keeps the screen language in the preview when the viewer session lands after the feed', async () => {
      const router = kioskRouter()
      await router.push('/infoscreen/preview/3')
      getInfoscreenPreviewFeed.mockResolvedValue(feedFixture({ language: 'deAT' }))
      const wrapper = mountWithApp(InfoscreenPreviewView, { pinia, global: { plugins: [router] } })
      await flushPromises()

      // As the session store does when /users/me answers.
      const currentUserStore = useCurrentUserStore()
      currentUserStore.$patch({ user: { language: 'enGB' } as never })
      i18n.global.locale.value = 'enGB'
      await flushPromises()
      expect(i18n.global.locale.value).toBe('deAT')

      wrapper.unmount()
      expect(i18n.global.locale.value).toBe('enGB')
    })
  })
})
