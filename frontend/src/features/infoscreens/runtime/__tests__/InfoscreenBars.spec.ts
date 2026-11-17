import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import { mountWithApp } from '@/test-utils/mountWithApp'

import InfoscreenScreen from '../components/InfoscreenScreen.vue'
import { LAYOUT_SLOT_COUNT } from '../types/infoscreenFeed'
import type { InfoscreenBar, InfoscreenFeedScreen, InfoscreenLayout } from '../types/infoscreenFeed'
import { feedFixture, pageFixture } from './infoscreenFixtures'

function screenWith(overrides: Partial<InfoscreenFeedScreen>) {
  const base = feedFixture()
  return feedFixture({ infoscreen: { ...base.infoscreen, ...overrides } })
}

function bar(overrides: Partial<InfoscreenBar>): InfoscreenBar {
  return { left: [], center: [], right: [], text: null, ...overrides } as InfoscreenBar
}

type Wrapper = ReturnType<ReturnType<typeof mountWithApp>['get']>

// The items of a bar or bar area, in DOM order, by their test ids.
function itemOrder(element: Wrapper): string[] {
  return element
    .findAll('[data-testid^="bar-"]:not([data-testid^="bar-area"])')
    .map((item) => item.attributes('data-testid')!)
}

describe('InfoscreenScreen bars', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-30T08:00:00Z'))
    i18n.global.locale.value = 'enGB'
    pinia = createPinia()
    setActivePinia(pinia)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('puts the header items into their areas in the order the screen lists them', () => {
    const feed = screenWith({
      header: bar({ left: ['text', 'clock'], center: ['title'], right: ['date'], text: 'Hall 2 North' }),
    })
    const wrapper = mountWithApp(InfoscreenScreen, { pinia, props: { feed } })

    const header = wrapper.get('[data-testid="infoscreen-header"]')
    expect(itemOrder(header.get('[data-testid="bar-area-left"]'))).toEqual(['bar-text', 'bar-clock'])
    expect(itemOrder(header.get('[data-testid="bar-area-center"]'))).toEqual(['bar-title'])
    expect(itemOrder(header.get('[data-testid="bar-area-right"]'))).toEqual(['bar-date'])
    expect(header.get('[data-testid="bar-title"]').text()).toBe('Hall 2')
    expect(header.get('[data-testid="bar-text"]').text()).toBe('Hall 2 North')
    expect(header.get('[data-testid="bar-date"]').text()).toContain('2026')
  })

  it('ticks the header clock on the device', async () => {
    const feed = screenWith({ header: bar({ right: ['clock'] }) })
    const wrapper = mountWithApp(InfoscreenScreen, { pinia, props: { feed } })
    const first = wrapper.get('[data-testid="bar-clock"]').text()

    await vi.advanceTimersByTimeAsync(60_000)

    expect(wrapper.get('[data-testid="bar-clock"]').text()).not.toBe(first)
  })

  it('shows the logo from the public branding and leaves it out without one', async () => {
    const feed = screenWith({ header: bar({ left: ['logo', 'title'] }) })
    const wrapper = mountWithApp(InfoscreenScreen, { pinia, props: { feed } })
    expect(wrapper.find('[data-testid="bar-logo"]').exists()).toBe(false)

    const branding = usePublicBrandingStore()
    branding.$patch({ branding: { app_name: 'Glados', has_logo: true } as never })
    await wrapper.vm.$nextTick()

    const logo = wrapper.get('[data-testid="bar-logo"]')
    expect(logo.attributes('src')).toContain('/api/v1/public/branding/logo')
    expect(logo.attributes('alt')).toBe('Glados')
  })

  it('shows the app name from the public branding and leaves it out when empty', async () => {
    const feed = screenWith({ header: bar({ left: ['app_name'] }) })
    const branding = usePublicBrandingStore()
    branding.$patch({ branding: { app_name: 'Werkhalle' } as never })
    const wrapper = mountWithApp(InfoscreenScreen, { pinia, props: { feed } })

    const name = wrapper.get('[data-testid="bar-app-name"]')
    expect(name.text()).toBe('Werkhalle')
    expect(name.classes()).toContain('bar-item')

    branding.$patch({ branding: { app_name: '' } as never })
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="bar-app-name"]').exists()).toBe(false)
  })

  it('shows the company name from the public branding and leaves it out when unset', async () => {
    const feed = screenWith({ header: bar({ left: ['company_name', 'title'] }) })
    const branding = usePublicBrandingStore()
    branding.$patch({ branding: { app_name: 'Glados', company_name: 'Acme Machining' } as never })
    const wrapper = mountWithApp(InfoscreenScreen, { pinia, props: { feed } })

    const name = wrapper.get('[data-testid="bar-company-name"]')
    expect(name.text()).toBe('Acme Machining')
    expect(name.classes()).toContain('bar-item')
    const header = wrapper.get('[data-testid="infoscreen-header"]')
    expect(itemOrder(header.get('[data-testid="bar-area-left"]'))).toEqual([
      'bar-company-name',
      'bar-title',
    ])

    branding.$patch({ branding: { app_name: 'Glados', company_name: null } as never })
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="bar-company-name"]').exists()).toBe(false)
  })

  it('puts the banner above the header', () => {
    const feed = feedFixture({ banner: { text: 'Fire drill', severity: 'danger' } })
    const wrapper = mountWithApp(InfoscreenScreen, { pinia, props: { feed } })

    const order = wrapper
      .findAll('[data-testid="infoscreen-banner"], [data-testid="infoscreen-header"]')
      .map((element) => element.attributes('data-testid'))
    expect(order).toEqual(['infoscreen-banner', 'infoscreen-header'])
  })

  it('hides the bars the screen switches off', () => {
    const feed = screenWith({ show_header: false, show_footer: false })
    const wrapper = mountWithApp(InfoscreenScreen, { pinia, props: { feed } })

    expect(wrapper.find('[data-testid="infoscreen-header"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="infoscreen-footer"]').exists()).toBe(false)
  })

  it('keeps all three areas so the center stays centred when one is empty', () => {
    const feed = screenWith({ header: bar({ center: ['title'] }) })
    const wrapper = mountWithApp(InfoscreenScreen, { pinia, props: { feed } })

    const areas = wrapper
      .get('[data-testid="infoscreen-header"]')
      .findAll('[data-testid^="bar-area"]')
      .map((area) => area.attributes('data-testid'))
    expect(areas).toEqual(['bar-area-left', 'bar-area-center', 'bar-area-right'])
  })

  it('shows the update time, the next holiday and the stale badge in the footer', () => {
    const base = screenWith({
      show_footer: true,
      footer: bar({ left: ['next_holiday'], right: ['last_updated'] }),
    })
    const feed = { ...base, next_holiday: { date: '2026-11-01', name: 'All Saints' } }
    const wrapper = mountWithApp(InfoscreenScreen, {
      pinia,
      props: { feed, staleSince: new Date('2026-10-30T07:45:00Z') },
    })

    const footer = wrapper.get('[data-testid="infoscreen-footer"]')
    expect(itemOrder(footer)).toEqual(['bar-holiday', 'bar-updated'])
    expect(footer.get('[data-testid="bar-holiday"]').text()).toContain('All Saints')
    expect(footer.get('[data-testid="bar-holiday"]').text()).toContain('in 2 days')
    expect(footer.get('[data-testid="bar-updated"]').text()).toMatch(/^Updated \d\d:00$/)
    // The stale badge closes the right area, after the right items.
    const right = footer.get('[data-testid="bar-area-right"]')
    const children = right.element.children
    expect((children[children.length - 1] as HTMLElement).dataset.testid).toBe('infoscreen-stale')
  })

  it('leaves out a next holiday item when the feed has none', () => {
    const feed = screenWith({
      show_footer: true,
      footer: bar({ center: ['next_holiday', 'text'] }),
    })
    const wrapper = mountWithApp(InfoscreenScreen, { pinia, props: { feed } })

    expect(itemOrder(wrapper.get('[data-testid="infoscreen-footer"]'))).toEqual([])
  })
})

describe('InfoscreenScreen layouts', () => {
  it.each([
    ['two_rows', 2],
    ['three_rows', 3],
    ['grid_2x3', 6],
    ['grid_3x2', 6],
  ] as [InfoscreenLayout, number][])('renders %s with %i slots', (layout, count) => {
    expect(LAYOUT_SLOT_COUNT[layout]).toBe(count)
    const slots = Array.from({ length: count }, (_, index) => ({
      type: 'message',
      title: null,
      text: `Slot ${index + 1}`,
      severity: 'info',
    }))
    const feed = screenWith({ pages: [pageFixture(layout, slots as never)] })
    const widgets = [slots.map(({ text }) => ({ type: 'message', text, severity: 'info' }))]
    const wrapper = mountWithApp(InfoscreenScreen, {
      props: { feed: { ...feed, widgets } as typeof feed },
    })

    expect(wrapper.get('[data-testid="infoscreen-page"]').classes()).toContain(
      `infoscreen-page--${layout}`,
    )
    const messages = wrapper.findAll('[data-testid="message-widget"]').map((m) => m.text())
    expect(messages).toEqual(slots.map(({ text }) => text))
  })
})
