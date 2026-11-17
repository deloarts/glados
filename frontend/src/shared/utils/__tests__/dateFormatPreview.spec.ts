import { describe, it, expect, vi, afterEach } from 'vitest'

import { formatISODateAs, formatISODateTimeAs } from '@/core/utils/dates'
import {
  DATE_FORMAT_SAMPLE,
  dateFormatSample,
  dateFormatSelectOptions,
  timezoneNowPreview,
} from '../dateFormatPreview'

afterEach(() => {
  vi.useRealTimers()
})

describe('dateFormatSelectOptions', () => {
  it('labels each preset with its own rendering of the sample', () => {
    expect(dateFormatSelectOptions(['iso', 'dmy_dot'])).toEqual([
      { value: 'iso', label: formatISODateAs(DATE_FORMAT_SAMPLE, 'iso') },
      { value: 'dmy_dot', label: formatISODateAs(DATE_FORMAT_SAMPLE, 'dmy_dot') },
    ])
  })
})

describe('dateFormatSample', () => {
  it('renders the sample with or without the time', () => {
    expect(dateFormatSample('dmy_dot')).toBe(formatISODateAs(DATE_FORMAT_SAMPLE, 'dmy_dot'))
    expect(dateFormatSample('dmy_dot', true)).toBe(
      formatISODateTimeAs(DATE_FORMAT_SAMPLE, 'dmy_dot'),
    )
  })

  it('is empty without a preset', () => {
    expect(dateFormatSample('')).toBe('')
    expect(dateFormatSample(null, true)).toBe('')
  })
})

describe('timezoneNowPreview', () => {
  it('shows the current 24-hour time in the zone', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-06T14:32:00Z'))
    expect(timezoneNowPreview('UTC')).toBe('14:32')
    expect(timezoneNowPreview('Europe/Vienna')).toBe('16:32')
  })

  it('is empty without a zone or for an unknown one', () => {
    expect(timezoneNowPreview('')).toBe('')
    expect(timezoneNowPreview(undefined)).toBe('')
    expect(timezoneNowPreview('Not/AZone')).toBe('')
  })
})
