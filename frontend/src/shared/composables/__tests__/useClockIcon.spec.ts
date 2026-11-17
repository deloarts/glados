import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import type { Ref } from 'vue'

import { setDisplayTimezone } from '@/core/utils/dates'
import { CLOCK_BASE_ICON, clockIconForMinutes, useClockIcon } from '../useClockIcon'

function at(time: string): Date {
  return new Date(`2026-10-06T${time}Z`)
}

function minutes(time: string): number {
  const [hours, mins] = time.split(':').map(Number)
  return (hours ?? 0) * 60 + (mins ?? 0)
}

let iconAtSetup: string | null = null

function mountClock() {
  let icon: Readonly<Ref<string>> | null = null
  const wrapper = mount(
    defineComponent({
      setup() {
        icon = useClockIcon()
        iconAtSetup = icon.value
        return () => h('i', { class: icon?.value })
      },
    }),
  )
  return { wrapper, icon: () => icon!.value }
}

describe('clockIconForMinutes', () => {
  it.each([
    ['10:30', 'mdi-clock-time-ten-outline'],
    ['10:31', 'mdi-clock-time-eleven-outline'],
    ['11:30', 'mdi-clock-time-eleven-outline'],
    ['11:31', 'mdi-clock-time-twelve-outline'],
    ['12:30', 'mdi-clock-time-twelve-outline'],
    ['23:31', 'mdi-clock-time-twelve-outline'],
    ['00:00', 'mdi-clock-time-twelve-outline'],
    ['00:30', 'mdi-clock-time-twelve-outline'],
    ['00:31', 'mdi-clock-time-one-outline'],
    ['06:15', 'mdi-clock-time-six-outline'],
  ])('shows the right hour icon at %s', (time, expected) => {
    expect(clockIconForMinutes(minutes(time))).toBe(expected)
  })
})

describe('useClockIcon', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setDisplayTimezone('UTC')
    iconAtSetup = null
  })

  afterEach(() => {
    vi.useRealTimers()
    setDisplayTimezone(null)
  })

  it('starts with the base icon and follows the time once mounted', () => {
    vi.setSystemTime(at('10:31:10'))
    const { wrapper, icon } = mountClock()

    expect(iconAtSetup).toBe(CLOCK_BASE_ICON)
    expect(icon()).toBe('mdi-clock-time-eleven-outline')

    wrapper.unmount()
  })

  it('uses the display timezone, not the browser zone', () => {
    setDisplayTimezone('Asia/Tokyo')
    vi.setSystemTime(at('01:45:00'))
    const { wrapper, icon } = mountClock()

    // 01:45 UTC is 10:45 in Tokyo.
    expect(icon()).toBe('mdi-clock-time-eleven-outline')

    wrapper.unmount()
  })

  it('keeps the base icon for an unknown timezone', () => {
    setDisplayTimezone('Not/AZone')
    vi.setSystemTime(at('10:31:10'))
    const { wrapper, icon } = mountClock()

    expect(icon()).toBe(CLOCK_BASE_ICON)

    wrapper.unmount()
  })

  it('switches exactly on the minute boundary', () => {
    vi.setSystemTime(at('10:30:30'))
    const { wrapper, icon } = mountClock()
    expect(icon()).toBe('mdi-clock-time-ten-outline')

    vi.advanceTimersByTime(29_999)
    expect(icon()).toBe('mdi-clock-time-ten-outline')

    vi.advanceTimersByTime(1)
    expect(icon()).toBe('mdi-clock-time-eleven-outline')
    expect(vi.getTimerCount()).toBe(1)

    wrapper.unmount()
  })

  it('re-aligns the timer when the tab becomes visible again', () => {
    vi.setSystemTime(at('10:29:30'))
    const { wrapper, icon } = mountClock()
    expect(icon()).toBe('mdi-clock-time-ten-outline')

    // The tab slept in the background past the next boundary without the
    // timer firing; becoming visible recomputes at once.
    vi.setSystemTime(at('10:30:50'))
    document.dispatchEvent(new Event('visibilitychange'))
    expect(icon()).toBe('mdi-clock-time-ten-outline')

    // The re-armed timer aims at 10:31:00, ten seconds away.
    vi.advanceTimersByTime(10_000)
    expect(icon()).toBe('mdi-clock-time-eleven-outline')

    wrapper.unmount()
  })

  it('clears its timer and listener on unmount', () => {
    vi.setSystemTime(at('10:30:30'))
    const { wrapper, icon } = mountClock()
    expect(vi.getTimerCount()).toBe(1)

    wrapper.unmount()
    expect(vi.getTimerCount()).toBe(0)

    vi.setSystemTime(at('11:45:00'))
    document.dispatchEvent(new Event('visibilitychange'))
    expect(icon()).toBe('mdi-clock-time-ten-outline')
  })
})
