import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { i18n } from '@/core/i18n'
import { mountWithApp } from '@/test-utils/mountWithApp'

import InfoscreenScreen from '../components/InfoscreenScreen.vue'
import InfoscreenWidget from '../components/InfoscreenWidget.vue'
import type { InfoscreenFeedPage } from '../types/infoscreenFeed'
import { feedFixture, lotRowFixture, orderCardFixture, pageFixture } from './infoscreenFixtures'

describe('InfoscreenScreen', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-30T08:00:00Z'))
    i18n.global.locale.value = 'enGB'
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders every widget of the first page from the feed', () => {
    const wrapper = mountWithApp(InfoscreenScreen, { props: { feed: feedFixture() } })

    const page = wrapper.get('[data-testid="infoscreen-page"]')
    expect(page.classes()).toContain('infoscreen-page--grid_2x2')
    expect(wrapper.findAll('[data-testid="machine-tile"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('DMG Mori 1')
    expect(wrapper.text()).toContain('Running')
    expect(wrapper.text()).toContain('Spindle repair')
    expect(wrapper.get('[data-testid="machine-current"]').text()).toContain('L-2026-0042')
    expect(wrapper.findAll('[data-testid="machine-next"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-testid="lot-row"]')).toHaveLength(3)
    expect(wrapper.text()).toContain('Lots Due')
    expect(wrapper.text()).toContain('Late in Hall 2')
    expect(wrapper.text()).toContain('3 days late')
    expect(wrapper.findAll('[data-testid="qa-row"]')).toHaveLength(1)
  })

  it('shows a customer only where the widget asks for it', () => {
    const wrapper = mountWithApp(InfoscreenScreen, { props: { feed: feedFixture() } })

    const [, dueRow, lateRow] = wrapper.findAll('[data-testid="lot-row"]')
    expect(dueRow!.text()).not.toContain('Acme Machines')
    expect(lateRow!.text()).toContain('Acme Machines')
  })

  it('rotates to the next page after rotation_seconds and starts over', async () => {
    const wrapper = mountWithApp(InfoscreenScreen, { props: { feed: feedFixture() } })
    expect(wrapper.get('[data-testid="infoscreen-page"]').attributes('data-page')).toBe('0')

    await vi.advanceTimersByTimeAsync(30_000)
    const second = wrapper.get('[data-testid="infoscreen-page"]')
    expect(second.attributes('data-page')).toBe('1')
    expect(second.classes()).toContain('infoscreen-page--main_side')
    expect(wrapper.findAll('[data-testid="delivery-row"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('Bearings Ltd')
    expect(wrapper.get('[data-testid="clock-holiday"]').text()).toContain('All Saints')

    await vi.advanceTimersByTimeAsync(30_000)
    expect(wrapper.get('[data-testid="infoscreen-page"]').attributes('data-page')).toBe('0')
  })

  it('does not rotate a screen with one page', async () => {
    const base = feedFixture()
    const feed = feedFixture({
      infoscreen: { ...base.infoscreen, pages: [base.infoscreen.pages[0]!] },
      widgets: [base.widgets[0]!],
    })
    const wrapper = mountWithApp(InfoscreenScreen, { props: { feed } })

    await vi.advanceTimersByTimeAsync(120_000)
    expect(wrapper.get('[data-testid="infoscreen-page"]').attributes('data-page')).toBe('0')
  })

  it('shows the banner on top and the stale badge with its time', () => {
    const wrapper = mountWithApp(InfoscreenScreen, {
      props: {
        feed: feedFixture({ banner: { text: 'Fire drill at 10:00', severity: 'warning' } }),
        staleSince: new Date('2026-10-30T07:45:00Z'),
      },
    })

    const banner = wrapper.get('[data-testid="infoscreen-banner"]')
    expect(banner.text()).toBe('Fire drill at 10:00')
    expect(banner.classes()).toContain('infoscreen-banner--warning')
    expect(wrapper.get('[data-testid="infoscreen-stale"]').text()).toMatch(/Stale since \d\d:45/)
  })

  it('gives a layout its full number of slots and leaves missing ones blank', () => {
    const base = feedFixture()
    const feed = feedFixture({
      infoscreen: {
        ...base.infoscreen,
        pages: [
          pageFixture('two_columns', [
            {
              type: 'message',
              title: null,
              text: 'Welcome',
              severity: 'info',
              text_align: 'left',
              vertical_align: 'middle',
            },
          ] as InfoscreenFeedPage['slots']),
        ],
      },
      widgets: [
        [
          {
            type: 'message',
            text: 'Welcome',
            severity: 'info',
            text_align: 'left',
            vertical_align: 'middle',
          },
        ],
      ],
    })
    const wrapper = mountWithApp(InfoscreenScreen, { props: { feed } })

    expect(wrapper.findAll('.infoscreen-slot')).toHaveLength(2)
    expect(wrapper.get('[data-testid="message-widget"]').text()).toBe('Welcome')
  })
})

describe('overdue lots and pool queues', () => {
  it('marks overdue lots among the due lots with how late they are', () => {
    const wrapper = mountWithApp(InfoscreenScreen, { props: { feed: feedFixture() } })

    const [overdue, due] = wrapper.findAll('[data-testid="lot-row"]')
    expect(overdue!.classes()).toContain('lot-row--late')
    expect(overdue!.get('[data-testid="lot-row-late"]').text()).toBe('2 days late')
    expect(due!.classes()).not.toContain('lot-row--late')
    expect(due!.find('[data-testid="lot-row-late"]').exists()).toBe(false)
  })

  it('shows what waits in a pool after the machines, with the rest as a count', () => {
    const wrapper = mountWithApp(InfoscreenScreen, { props: { feed: feedFixture() } })

    const pools = wrapper.findAll('[data-testid="machine-pool"]')
    expect(pools).toHaveLength(1)
    expect(pools[0]!.text()).toContain('Waiting in pool Lasers')
    const cards = pools[0]!.findAll('[data-testid="machine-pool-card"]')
    // Each card shows the lot number on its first line, then part number and name.
    expect(cards.map((card) => card.findAll('.order-card-line')[0]!.text())).toEqual([
      'L-2026-0060',
      'L-2026-0061',
    ])
    expect(cards[0]!.find('[data-testid="row-thumbnail"]').exists()).toBe(true)
    expect(cards[1]!.find('[data-testid="row-thumbnail-placeholder"]').exists()).toBe(true)
    expect(pools[0]!.get('[data-testid="machine-pool-more"]').text()).toBe('+3 more')

    // The pools come after the machine tiles.
    const board = wrapper.get('.machine-board').element
    expect(board.lastElementChild?.getAttribute('data-testid')).toBe('machine-pool')
  })

  it('shows no count when every waiting order is listed', () => {
    const wrapper = mountWithApp(InfoscreenWidget, {
      props: {
        config: { type: 'machine_board', title: null, machine_ids: [], pool_ids: [4], next_count: 3 },
        data: {
          type: 'machine_board',
          machines: [],
          pools: [{ pool_id: 4, pool_name: 'Lasers', waiting: [orderCardFixture()], waiting_total: 1 }],
        },
      } as never,
    })

    expect(wrapper.findAll('[data-testid="machine-pool"]')).toHaveLength(1)
    expect(wrapper.find('[data-testid="machine-pool-more"]').exists()).toBe(false)
  })
})

describe('row thumbnails', () => {
  it('starts every row and machine card with the item picture or a placeholder', () => {
    const wrapper = mountWithApp(InfoscreenScreen, { props: { feed: feedFixture() } })

    const current = wrapper.get('[data-testid="machine-current"]')
    const image = current.get('[data-testid="row-thumbnail"]')
    expect(image.attributes('src')).toBe('/api/v1/web/terminal-device/thumbnails/card-token')
    expect(image.attributes('loading')).toBe('lazy')
    expect(wrapper.get('[data-testid="machine-next"]').find('[data-testid="row-thumbnail"]').exists()).toBe(true)

    const lotRow = wrapper.get('[data-testid="lot-row"]')
    expect(lotRow.element.firstElementChild?.querySelector('img')?.getAttribute('src')).toBe(
      '/api/v1/web/terminal-device/thumbnails/lot-token',
    )

    // The QA task of the fixture has no picture.
    const qaRow = wrapper.get('[data-testid="qa-row"]')
    expect(qaRow.find('[data-testid="row-thumbnail"]').exists()).toBe(false)
    expect(qaRow.find('[data-testid="row-thumbnail-placeholder"]').exists()).toBe(true)
  })

  it('falls back to the placeholder when the picture fails to load', async () => {
    const wrapper = mountWithApp(InfoscreenWidget, {
      props: {
        config: { type: 'lots_due', title: null, horizon_days: 7, pool_ids: [], show_customer: false },
        data: { type: 'lots_due', lots: [lotRowFixture()] },
      },
    })

    await wrapper.get('[data-testid="row-thumbnail"]').trigger('error')

    expect(wrapper.find('[data-testid="row-thumbnail"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="row-thumbnail-placeholder"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="lot-row"]').text()).toContain('L-2026-0050')
  })

  it('tries a new picture again after a failed one', async () => {
    const config = { type: 'lots_due', title: null, horizon_days: 7, pool_ids: [], show_customer: false }
    const wrapper = mountWithApp(InfoscreenWidget, {
      props: { config, data: { type: 'lots_due', lots: [lotRowFixture()] } } as never,
    })
    await wrapper.get('[data-testid="row-thumbnail"]').trigger('error')

    await wrapper.setProps({
      data: { type: 'lots_due', lots: [lotRowFixture({ thumbnail_url: '/thumbnails/new' })] },
    } as never)

    expect(wrapper.get('[data-testid="row-thumbnail"]').attributes('src')).toBe('/thumbnails/new')
  })
})

describe('InfoscreenWidget', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-30T08:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('ticks the clock every second on the device', async () => {
    const wrapper = mountWithApp(InfoscreenWidget, {
      props: {
        config: {
          type: 'clock',
          title: null,
          show_date: true,
          show_next_holiday: false,
          show_seconds: true,
          style: 'digital',
        },
        data: null,
      },
    })
    const first = wrapper.get('[data-testid="clock-time"]').text()

    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()

    expect(wrapper.get('[data-testid="clock-time"]').text()).not.toBe(first)
    expect(wrapper.find('[data-testid="clock-date"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="clock-holiday"]').exists()).toBe(false)
  })

  it('says so when the feed has no data for a widget', () => {
    const wrapper = mountWithApp(InfoscreenWidget, {
      props: { config: { type: 'qa_queue', title: 'QA' }, data: null },
    })

    expect(wrapper.text()).toContain('No data')
  })

  it('shows the empty text of a list without rows', () => {
    const wrapper = mountWithApp(InfoscreenWidget, {
      props: {
        config: { type: 'late_lots', title: null, show_customer: false },
        data: { type: 'late_lots', lots: [] },
      },
    })

    expect(wrapper.text()).toContain('No late lots')
    expect(wrapper.get('[data-testid="widget-count"]').text()).toBe('0')
  })

  it('shows the target date of a due lot', () => {
    const wrapper = mountWithApp(InfoscreenWidget, {
      props: {
        config: { type: 'lots_due', title: null, horizon_days: 7, pool_ids: [], show_customer: false },
        data: { type: 'lots_due', lots: [lotRowFixture({ target_date: '2026-11-02' })] },
      },
    })

    expect(wrapper.get('[data-testid="lot-row"]').text()).toContain('2026')
    expect(wrapper.get('[data-testid="lot-row"]').text()).toContain('Planned')
  })
})
