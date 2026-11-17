import { describe, it, expect, afterEach } from 'vitest'

import { i18n } from '@/core/i18n'
import { setDisplayTimezone } from '@/core/utils/dates'
import { useLocaleFormat } from '../useLocaleFormat'

describe('useLocaleFormat', () => {
  afterEach(() => {
    i18n.global.locale.value = 'enGB'
    setDisplayTimezone(null)
  })

  describe('timezone', () => {
    const value = new Date(Date.UTC(2026, 7, 6, 14, 32, 0))
    const clock: Intl.DateTimeFormatOptions = { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }

    it('renders in the display timezone when the options name none', () => {
      setDisplayTimezone('Asia/Tokyo')

      expect(useLocaleFormat().formatTime(value, clock)).toBe('23:32')
    })

    it('lets an explicit timeZone option win over the display timezone', () => {
      setDisplayTimezone('Asia/Tokyo')

      expect(useLocaleFormat().formatTime(value, { ...clock, timeZone: 'UTC' })).toBe('14:32')
    })
  })

  describe('formatNumber', () => {
    it('uses a period thousands separator for en-GB', () => {
      const { formatNumber } = useLocaleFormat()

      expect(formatNumber(1234.5)).toBe('1,234.5')
    })

    it('uses a comma decimal separator for de-AT', () => {
      i18n.global.locale.value = 'deAT'
      const { formatNumber } = useLocaleFormat()

      // de-AT groups thousands with a non-breaking space, not a period.
      expect(formatNumber(1234.5)).toBe('1 234,5')
    })

    it('forwards Intl.NumberFormatOptions, e.g. fixed fraction digits', () => {
      const { formatNumber } = useLocaleFormat()

      expect(
        formatNumber(3, { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
      ).toBe('3.00')
    })

    it('accepts an explicit locale override regardless of the active UI language', () => {
      const { formatNumber } = useLocaleFormat('deAT')

      expect(formatNumber(1234.5)).toBe('1 234,5')
    })
  })

  describe('formatDate', () => {
    it('renders day/month/year order for en-GB by default', () => {
      const { formatDate } = useLocaleFormat()

      expect(formatDate(new Date(Date.UTC(2026, 7, 6)), { timeZone: 'UTC' })).toBe('06/08/2026')
    })

    it('renders day.month.year order for de-AT', () => {
      i18n.global.locale.value = 'deAT'
      const { formatDate } = useLocaleFormat()

      expect(
        formatDate(new Date(Date.UTC(2026, 7, 6)), {
          timeZone: 'UTC',
          day: '2-digit',
          month: '2-digit',
          year: 'numeric',
        }),
      ).toBe('06.08.2026')
    })
  })

  describe('formatTime', () => {
    it('defaults to a medium time style when no options are given', () => {
      const { formatTime } = useLocaleFormat()

      const result = formatTime(new Date(Date.UTC(2026, 7, 6, 14, 32, 0)), undefined)
      expect(typeof result).toBe('string')
      expect(result.length).toBeGreaterThan(0)
    })

    it('forwards explicit options, e.g. a fixed UTC 24-hour time', () => {
      const { formatTime } = useLocaleFormat()

      const result = formatTime(new Date(Date.UTC(2026, 7, 6, 14, 32, 0)), {
        timeZone: 'UTC',
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23',
      })
      expect(result).toBe('14:32')
    })
  })

  describe('formatDateTime', () => {
    it('combines date and time for en-GB and de-AT differently', () => {
      const value = new Date(Date.UTC(2026, 7, 6, 14, 32, 0))

      const en = useLocaleFormat().formatDateTime(value, {
        timeZone: 'UTC',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23',
      })

      i18n.global.locale.value = 'deAT'
      const de = useLocaleFormat().formatDateTime(value, {
        timeZone: 'UTC',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23',
      })

      expect(en).toBe('06/08/2026, 14:32')
      expect(de).toBe('06.08.2026, 14:32')
    })
  })
})
