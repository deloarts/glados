import { describe, it, expect, afterEach, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { setDisplayTimezone } from '@/core/utils/dates'
import TimeTrackingMonthTable from '../TimeTrackingMonthTable.vue'
import type { TimeTrackingDay } from '../../types/timeTrackingTypes'

function day(date: string, overrides: Partial<TimeTrackingDay> = {}): TimeTrackingDay {
  return {
    date,
    weekday: new Date(`${date}T00:00:00Z`).getUTCDay() || 7,
    shift_name: 'Full time 38.5h',
    shift_short_name: 'FT',
    first_in: `${date}T07:00:00Z`,
    last_out: `${date}T15:00:00Z`,
    bookings: [
      { at: `${date}T07:00:00Z`, direction: 'in' },
      { at: `${date}T15:00:00Z`, direction: 'out' },
    ],
    worked_seconds: 8 * 3600,
    target_seconds: 8 * 3600,
    day_balance_seconds: 0,
    running_balance_seconds: 0,
    status: 'normal',
    ...overrides,
  }
}

const DAYS = [
  day('2026-10-02', { day_balance_seconds: -(15 * 60), running_balance_seconds: -(15 * 60) }),
  day('2026-10-03', {
    first_in: null,
    last_out: null,
    bookings: [],
    worked_seconds: null,
    target_seconds: 0,
    day_balance_seconds: null,
    status: 'shift_free',
  }),
  day('2026-10-05', { day_balance_seconds: 42 * 60 }),
]

function rowFor(wrapper: ReturnType<typeof mountWithApp>, date: string) {
  return wrapper.findAll('tbody tr').find((row) => row.text().includes(date))!
}

describe('TimeTrackingMonthTable', () => {
  beforeEach(() => setDisplayTimezone('UTC'))
  afterEach(() => setDisplayTimezone(null))

  it('mutes weekends, highlights today and shows negative balances in the danger colour', async () => {
    const wrapper = mountWithApp(TimeTrackingMonthTable, {
      props: { days: DAYS, todayDate: '2026-10-05' },
    })
    await flushPromises()

    expect(rowFor(wrapper, '2026-10-03').classes()).toContain('tt-row--muted')
    expect(rowFor(wrapper, '2026-10-05').classes()).toContain('tt-row--today')
    expect(rowFor(wrapper, '2026-10-02').classes()).not.toContain('tt-row--muted')

    const negative = rowFor(wrapper, '2026-10-02').findAll('.is-negative')
    expect(negative.map((cell) => cell.text())).toEqual(['-0:15', '-0:15'])
    expect(rowFor(wrapper, '2026-10-05').text()).toContain('+0:42')

    wrapper.unmount()
  })

  it('folds out the bookings of a day on demand', async () => {
    const wrapper = mountWithApp(TimeTrackingMonthTable, {
      props: { days: DAYS, todayDate: null },
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="time-tracking-booking-list-2026-10-02"]').exists()).toBe(false)

    await wrapper.find('[data-testid="time-tracking-bookings-2026-10-02"]').trigger('click')
    await flushPromises()

    const list = wrapper.find('[data-testid="time-tracking-booking-list-2026-10-02"]')
    expect(list.text()).toContain('07:00')
    expect(list.text()).toContain('15:00')

    wrapper.unmount()
  })
})
