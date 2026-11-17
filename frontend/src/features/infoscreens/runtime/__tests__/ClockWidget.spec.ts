import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { setDisplayTimezone } from '@/core/utils/dates'
import { mountWithApp } from '@/test-utils/mountWithApp'

import ClockWidget from '../components/widgets/ClockWidget.vue'
import type { WidgetConfigOf } from '../types/infoscreenFeed'

type ClockConfig = WidgetConfigOf<'clock'>

function clockConfig(overrides: Partial<ClockConfig> = {}): ClockConfig {
  return {
    type: 'clock',
    title: null,
    show_date: false,
    show_next_holiday: false,
    show_seconds: false,
    style: 'digital',
    ...overrides,
  } as ClockConfig
}

function mountClock(config: ClockConfig) {
  return mountWithApp(ClockWidget, {
    props: { config, data: { type: 'clock', next_holiday: { date: '2026-11-01', name: 'All Saints' } } },
  })
}

function angleOf(wrapper: ReturnType<typeof mountClock>, hand: string): number {
  const transform = wrapper.get(`[data-testid="clock-hand-${hand}"]`).attributes('transform') ?? ''
  return Number(/rotate\(([-\d.]+)/.exec(transform)?.[1])
}

function digits(wrapper: ReturnType<typeof mountClock>) {
  return wrapper.findAll('[data-testid="binary-digit"]').map((column) => ({
    digit: column.attributes('data-digit'),
    dots: column.findAll('[data-testid="binary-dot"]').map((dot) => dot.classes().includes('binary-clock-dot--lit')),
  }))
}

describe('ClockWidget', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // 14:37:25 in UTC, the display timezone of these tests.
    vi.setSystemTime(new Date('2026-10-30T14:37:25Z'))
    setDisplayTimezone('UTC')
  })

  afterEach(() => {
    setDisplayTimezone(null)
    vi.useRealTimers()
  })

  it('shows hours and minutes digitally, with the seconds only when asked', async () => {
    const plain = mountClock(clockConfig())
    expect(plain.get('[data-testid="clock-time"]').text()).toBe('14:37')
    expect(plain.find('[data-testid="clock-seconds"]').exists()).toBe(false)

    const withSeconds = mountClock(clockConfig({ show_seconds: true }))
    expect(withSeconds.get('[data-testid="clock-seconds"]').text()).toBe('25')
    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()
    expect(withSeconds.get('[data-testid="clock-seconds"]').text()).toBe('26')
  })

  it('reads a config without style and seconds as the digital clock without seconds', () => {
    const config = clockConfig()
    delete (config as Partial<ClockConfig>).style
    delete (config as Partial<ClockConfig>).show_seconds

    const wrapper = mountClock(config)

    expect(wrapper.get('[data-testid="clock-time"]').text()).toBe('14:37')
  })

  it('draws an analogue face with the hands at the time', () => {
    const wrapper = mountClock(clockConfig({ style: 'analogue' }))

    expect(wrapper.find('[data-testid="clock-analogue"]').exists()).toBe(true)
    expect(wrapper.findAll('.analogue-clock-tick')).toHaveLength(60)
    // 14:37 is 2:37 on the dial: (2 + 37 / 60) * 30 degrees.
    expect(angleOf(wrapper, 'hour')).toBeCloseTo(78.5)
    expect(angleOf(wrapper, 'minute')).toBe(222)
    expect(wrapper.find('[data-testid="clock-hand-second"]').exists()).toBe(false)
  })

  it('adds a moving second hand to the analogue face when seconds are on', async () => {
    const wrapper = mountClock(clockConfig({ style: 'analogue', show_seconds: true }))
    expect(angleOf(wrapper, 'second')).toBe(150)

    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()

    expect(angleOf(wrapper, 'second')).toBe(156)
  })

  it('shows a binary-coded-decimal column per digit of hours and minutes', () => {
    const wrapper = mountClock(clockConfig({ style: 'binary' }))

    // Top dot first: tens of hours have 2 dots, tens of minutes 3, ones 4.
    expect(digits(wrapper)).toEqual([
      { digit: '1', dots: [false, true] },
      { digit: '4', dots: [false, true, false, false] },
      { digit: '3', dots: [false, true, true] },
      { digit: '7', dots: [false, true, true, true] },
    ])
  })

  it('adds the seconds columns to the binary clock when seconds are on', () => {
    const wrapper = mountClock(clockConfig({ style: 'binary', show_seconds: true }))

    expect(digits(wrapper).slice(4)).toEqual([
      { digit: '2', dots: [false, true, false] },
      { digit: '5', dots: [false, true, false, true] },
    ])
  })

  it.each(['digital', 'analogue', 'binary'] as const)(
    'shows the date and the next holiday in the %s style when asked',
    (style) => {
      const wrapper = mountClock(clockConfig({ style, show_date: true, show_next_holiday: true }))

      expect(wrapper.get('[data-testid="clock-date"]').text()).toContain('2026')
      expect(wrapper.get('[data-testid="clock-holiday"]').text()).toContain('All Saints')
    },
  )
})
