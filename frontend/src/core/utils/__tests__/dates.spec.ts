import { describe, it, expect, afterEach } from 'vitest'
import {
  DATE_FORMATS,
  dateToParam,
  formatISODate,
  formatISODateAs,
  formatISODateTime,
  formatISODateTimeAs,
  formatISOTime,
  formatPlanned,
  getDisplayDateFormat,
  getDisplayTimezone,
  endOfDayInDisplayZone,
  getPickerDateFormat,
  instantToPickerDate,
  isCalendarDate,
  localeTag,
  parseBackendTimestamp,
  pickerDateToInstant,
  setDisplayDateFormat,
  setDisplayTimezone,
  toDayKey,
  toLocalDayStart,
  toWallClockDate,
  todayKey,
  todayStart,
} from '@/core/utils/dates'
import { i18n } from '@/core/i18n'

afterEach(() => {
  // Display timezone and date format are module-level state (set once from the
  // host capabilities and the logged-in user); leaking them between cases
  // would make these order-dependent.
  setDisplayTimezone(null)
  setDisplayDateFormat(null)
})

describe('parseBackendTimestamp', () => {
  it('treats a naive (no Z) datetime string as UTC, not local', () => {
    const parsed = parseBackendTimestamp('2026-07-19T22:00:00')
    expect(parsed.toISOString()).toBe('2026-07-19T22:00:00.000Z')
  })

  it('leaves an already-Z-suffixed datetime untouched', () => {
    const parsed = parseBackendTimestamp('2026-07-19T22:00:00.000Z')
    expect(parsed.toISOString()).toBe('2026-07-19T22:00:00.000Z')
  })

  it('leaves a bare date-only string untouched (already correctly UTC per spec)', () => {
    const parsed = parseBackendTimestamp('2026-07-19')
    expect(parsed.toISOString()).toBe('2026-07-19T00:00:00.000Z')
  })

  it('respects an explicit +HH:MM offset, which the event columns now send', () => {
    // What a `timestamptz` column actually serializes to.
    const parsed = parseBackendTimestamp('2026-08-06T16:32:11.123456+02:00')
    expect(parsed.toISOString()).toBe('2026-08-06T14:32:11.123Z')
  })
})

describe('localeTag', () => {
  afterEach(() => {
    i18n.global.locale.value = 'enGB'
  })

  it('maps the current UI locale to its BCP-47 tag', () => {
    i18n.global.locale.value = 'enGB'
    expect(localeTag()).toBe('en-GB')
    i18n.global.locale.value = 'deAT'
    expect(localeTag()).toBe('de-AT')
  })

  it('accepts an explicit override, ignoring the current UI locale', () => {
    i18n.global.locale.value = 'enGB'
    expect(localeTag('deAT')).toBe('de-AT')
    i18n.global.locale.value = 'deAT'
    expect(localeTag('enGB')).toBe('en-GB')
  })
})

describe('isCalendarDate', () => {
  it('distinguishes a picked day from a recorded instant', () => {
    expect(isCalendarDate('2026-08-06')).toBe(true)
    expect(isCalendarDate('2026-08-06T14:32:11+00:00')).toBe(false)
  })
})

describe('getDisplayTimezone', () => {
  it('falls back to the browser zone before the tenant timezone is known', () => {
    setDisplayTimezone(null)
    expect(getDisplayTimezone()).toBe(Intl.DateTimeFormat().resolvedOptions().timeZone)
  })

  it('prefers the tenant timezone once set, and treats "" as unset', () => {
    setDisplayTimezone('Asia/Tokyo')
    expect(getDisplayTimezone()).toBe('Asia/Tokyo')
    setDisplayTimezone('')
    expect(getDisplayTimezone()).toBe(Intl.DateTimeFormat().resolvedOptions().timeZone)
  })
})

describe('toDayKey', () => {
  it('resolves an instant to the day it falls on in the display timezone', () => {
    // 23:30 UTC is already the next day in Vienna (+02:00 in August) and
    // still the same day in New York.
    setDisplayTimezone('Europe/Vienna')
    expect(toDayKey('2026-08-06T23:30:00+00:00')).toBe('2026-08-07')

    setDisplayTimezone('America/New_York')
    expect(toDayKey('2026-08-06T23:30:00+00:00')).toBe('2026-08-06')
  })

  it('never shifts a calendar date, whatever the timezone', () => {
    // The off-by-one this guards against: 6 August is 6 August everywhere,
    // so a picked date must not be pushed to the 5th in a western zone.
    for (const zone of ['Europe/Vienna', 'America/Los_Angeles', 'Pacific/Kiritimati']) {
      setDisplayTimezone(zone)
      expect(toDayKey('2026-08-06')).toBe('2026-08-06')
    }
  })
})

describe('formatISODate / formatISODateTime / formatISOTime', () => {
  it('renders an instant against the display timezone', () => {
    setDisplayTimezone('Australia/Sydney')
    // 22:00 UTC on the 6th is 08:00 on the 7th in Sydney (+10:00).
    expect(formatISODate('2026-08-06T22:00:00+00:00')).toContain('7')
    expect(formatISOTime('2026-08-06T22:00:00+00:00')).toMatch(/8|08/)
  })

  it('renders a calendar date verbatim, with no timezone shift', () => {
    setDisplayTimezone('America/Los_Angeles')
    // Would read as 5 August if it were shifted into LA time.
    expect(formatISODate('2026-08-06')).toContain('6')
  })

  it('has no time to show for a calendar date, so does not invent 00:00', () => {
    setDisplayTimezone('Europe/Vienna')
    expect(formatISOTime('2026-08-06')).toBe('')
    expect(formatISODateTime('2026-08-06')).toBe(formatISODate('2026-08-06'))
  })
})

describe('toLocalDayStart', () => {
  it('returns local midnight for the day the value falls on', () => {
    setDisplayTimezone('Europe/Vienna')
    const day = toLocalDayStart('2026-08-06T23:30:00+00:00')
    expect(day.getHours()).toBe(0)
    expect(day.getMinutes()).toBe(0)
    // 23:30 UTC is already the 7th in Vienna.
    expect(day.getDate()).toBe(7)
  })

  it('puts an instant and a calendar date for the same day on the same footing', () => {
    setDisplayTimezone('Europe/Vienna')
    const fromInstant = toLocalDayStart('2026-08-06T09:15:00+00:00')
    const fromCalendarDate = toLocalDayStart('2026-08-06')
    expect(fromInstant.getTime()).toBe(fromCalendarDate.getTime())
  })
})

describe('date format presets', () => {
  const INSTANT = '2026-08-06T14:32:00+00:00'

  it('renders each preset as its documented shape', () => {
    setDisplayTimezone('UTC')
    const rendered = Object.fromEntries(
      DATE_FORMATS.map((preset) => {
        setDisplayDateFormat(preset)
        return [preset, formatISODate(INSTANT)]
      }),
    )
    expect(rendered).toEqual({
      iso: '2026-08-06',
      dmy_dot: '06.08.2026',
      dmy_slash: '06/08/2026',
      mdy_slash: '08/06/2026',
      d_mon_y: '06 Aug 2026',
    })
  })

  it('is independent of the browser locale', () => {
    // The point of presets over a locale passthrough: one preset means exactly
    // one shape, whatever Intl's default locale happens to be here.
    setDisplayTimezone('UTC')
    setDisplayDateFormat('dmy_dot')
    expect(formatISODate(INSTANT)).toBe('06.08.2026')
  })

  it('applies the preset to calendar dates too, without a timezone shift', () => {
    setDisplayTimezone('America/Los_Angeles')
    setDisplayDateFormat('dmy_dot')
    // Would read 05.08.2026 if a picked date were shifted into LA time.
    expect(formatISODate('2026-08-06')).toBe('06.08.2026')
  })

  it('falls back to ISO for an unknown or missing preset', () => {
    setDisplayTimezone('UTC')
    setDisplayDateFormat('dd.MM.yyyy')
    expect(getDisplayDateFormat()).toBe('iso')
    expect(formatISODate(INSTANT)).toBe('2026-08-06')

    setDisplayDateFormat(null)
    expect(getDisplayDateFormat()).toBe('iso')
  })

  it('combines the preset with a 24-hour time, in the display timezone', () => {
    setDisplayTimezone('Europe/Vienna')
    setDisplayDateFormat('dmy_dot')
    // 14:32 UTC is 16:32 in Vienna (+02:00 in August).
    expect(formatISODateTime(INSTANT)).toBe('06.08.2026 16:32')
  })

  it('always renders time 24-hour, never AM/PM', () => {
    setDisplayTimezone('UTC')
    for (const iso of ['2026-08-06T14:32:00+00:00', '2026-08-06T00:05:00+00:00']) {
      const time = formatISOTime(iso)
      expect(time).not.toMatch(/[AaPp]\.?[Mm]/)
    }
    expect(formatISOTime('2026-08-06T14:32:00+00:00')).toBe('14:32')
    expect(formatISOTime('2026-08-06T00:05:00+00:00')).toBe('00:05')
  })

  it('formats an explicit preset without touching the live preference', () => {
    // Previewing a preset by temporarily writing the live preference, inside
    // a computed that also reads it, would make the effect mutate its own
    // dependency and Vue would throw "Maximum recursive updates exceeded" the
    // moment the format changes.
    setDisplayTimezone('UTC')
    setDisplayDateFormat('iso')

    expect(formatISODateAs(INSTANT, 'dmy_dot')).toBe('06.08.2026')
    expect(formatISODateTimeAs(INSTANT, 'mdy_slash')).toBe('08/06/2026 14:32')

    // The preference is exactly where it was.
    expect(getDisplayDateFormat()).toBe('iso')
    expect(formatISODate(INSTANT)).toBe('2026-08-06')
  })

  it('previews every preset at once without the preference drifting', () => {
    setDisplayTimezone('UTC')
    setDisplayDateFormat('d_mon_y')
    const labels = DATE_FORMATS.map((preset) => formatISODateAs(INSTANT, preset))
    expect(labels).toHaveLength(DATE_FORMATS.length)
    expect(getDisplayDateFormat()).toBe('d_mon_y')
  })

  it('maps every preset to a OpenVue picker token', () => {
    const tokens = DATE_FORMATS.map((preset) => {
      setDisplayDateFormat(preset)
      return getPickerDateFormat()
    })
    expect(tokens).toEqual(['yy-mm-dd', 'dd.mm.yy', 'dd/mm/yy', 'mm/dd/yy', 'dd M yy'])
  })
})

describe('dateToParam', () => {
  // The load-bearing boundary: this feeds API query params and request bodies,
  // and the backend speaks YYYY-MM-DD. If a display preference ever leaked in
  // here, date-range filters would silently return the wrong rows.
  it('stays ISO regardless of the display format preference', () => {
    const day = new Date(2026, 7, 6)
    for (const preset of DATE_FORMATS) {
      setDisplayDateFormat(preset)
      expect(dateToParam(day)).toBe('2026-08-06')
    }
  })

  it('returns null for null, so an unset filter bound stays unset', () => {
    setDisplayDateFormat('mdy_slash')
    expect(dateToParam(null)).toBeNull()
  })

  // dateToParam serves OrderFieldEditDialog and OrderItemsTable: null,
  // midnight and a DST boundary are the three cases they depend on.
  it('formats an explicit midnight the same as any other time on the day', () => {
    expect(dateToParam(new Date(2026, 7, 6, 0, 0, 0, 0))).toBe('2026-08-06')
  })

  it('stays on the correct calendar day across a DST spring-forward boundary', () => {
    // Europe/Berlin (the test runner's default zone) jumps from 02:00 to
    // 03:00 on 2026-03-29; 02:30 local never occurs and is normalized
    // forward by the engine, but the calendar day must still read the 29th.
    expect(dateToParam(new Date(2026, 2, 29, 2, 30, 0))).toBe('2026-03-29')
  })

  it('stays on the correct calendar day across a DST fall-back boundary', () => {
    // 2026-10-25 02:30 is the ambiguous local hour that occurs twice as
    // clocks fall back from 03:00 to 02:00; either occurrence must still
    // read the 25th.
    expect(dateToParam(new Date(2026, 9, 25, 2, 30, 0))).toBe('2026-10-25')
  })
})

describe('formatPlanned', () => {
  // Shared by LotRecordPositionCard.vue and ProductionOrderDetailDialog.vue
  // for planned/actual/not-before fields in the production detail views.
  it('renders the empty placeholder for null', () => {
    expect(formatPlanned(null)).toBe('-')
  })

  it('renders a calendar date verbatim', () => {
    expect(formatPlanned('2026-08-06')).toBe('2026-08-06')
  })

  it('renders an instant as the plain date it falls on', () => {
    expect(formatPlanned('2026-08-06T10:00:00+00:00')).toBe('2026-08-06')
  })
})

describe('toDayKey (format independence)', () => {
  it('stays ISO regardless of the display format preference', () => {
    // Grouping/bucketing keys are internal, not display, a preset must not
    // change them or day comparisons would break.
    setDisplayTimezone('Europe/Vienna')
    for (const preset of DATE_FORMATS) {
      setDisplayDateFormat(preset)
      expect(toDayKey('2026-08-06T09:15:00+00:00')).toBe('2026-08-06')
    }
  })
})

describe('formatISODateAs / formatISODateTimeAs purity', () => {
  // Previewing a preset by briefly writing the live preference and restoring
  // it, inside a `computed` that also reads the preference, would make the
  // effect mutate its own dependency, and Vue would throw "Maximum recursive
  // updates exceeded" the moment the format changes. These take the preset
  // as an argument precisely so previewing is pure.
  it('leaves the live preference untouched', () => {
    setDisplayDateFormat('iso')
    for (const preset of DATE_FORMATS) {
      formatISODateAs('2026-08-06T14:32:00+00:00', preset)
      formatISODateTimeAs('2026-08-06T14:32:00+00:00', preset)
      expect(getDisplayDateFormat()).toBe('iso')
    }
  })

  it('renders every preset in one pass, as a settings preview does', () => {
    setDisplayTimezone('UTC')
    setDisplayDateFormat('mdy_slash')
    const labels = DATE_FORMATS.map((p) => formatISODateAs('2026-08-06T14:32:00+00:00', p))
    // All five distinct, and the live preference still what it was.
    expect(new Set(labels).size).toBe(DATE_FORMATS.length)
    expect(getDisplayDateFormat()).toBe('mdy_slash')
  })
})

// The display zones picked here sit far from the machine's own zone, so each
// case shows the tenant zone winning over the browser's.
describe('today in the display timezone', () => {
  // 03:30 UTC on 7 August is still the 6th in New York and already the 7th
  // in Tokyo, whatever the browser says.
  const now = new Date('2026-08-07T03:30:00Z')

  it('takes the day from the display timezone, not the browser', () => {
    setDisplayTimezone('America/New_York')
    expect(todayKey(now)).toBe('2026-08-06')

    setDisplayTimezone('Asia/Tokyo')
    expect(todayKey(now)).toBe('2026-08-07')
  })

  it('returns local midnight on that day, for local calendar arithmetic', () => {
    setDisplayTimezone('America/New_York')
    const start = todayStart(now)
    expect(dateToParam(start)).toBe('2026-08-06')
    expect([start.getHours(), start.getMinutes()]).toEqual([0, 0])
  })
})

describe('pickers on the display timezone wall clock', () => {
  it('shows an instant with the fields of the display timezone', () => {
    setDisplayTimezone('America/New_York')
    // 14:32 UTC is 10:32 in New York (-04:00 in August).
    const picked = instantToPickerDate('2026-08-06T14:32:00Z')
    expect(dateToParam(picked)).toBe('2026-08-06')
    expect([picked.getHours(), picked.getMinutes()]).toEqual([10, 32])
  })

  it('reads a picker value back as the instant on the display timezone wall clock', () => {
    setDisplayTimezone('Asia/Tokyo')
    // 08:15 on 6 August in Tokyo (+09:00) is 23:15 UTC on the 5th.
    const instant = pickerDateToInstant(new Date(2026, 7, 6, 8, 15))
    expect(instant.toISOString()).toBe('2026-08-05T23:15:00.000Z')
  })

  it('round-trips an instant, across a daylight saving change too', () => {
    setDisplayTimezone('Europe/Vienna')
    // Before and after the October switch from +02:00 to +01:00.
    for (const iso of ['2026-10-24T22:30:00.000Z', '2026-10-25T03:30:00.000Z']) {
      expect(pickerDateToInstant(instantToPickerDate(iso)).toISOString()).toBe(iso)
    }
  })

  it('ends a picked day at midnight on the display timezone wall clock', () => {
    setDisplayTimezone('America/New_York')
    const end = endOfDayInDisplayZone(new Date(2026, 7, 6))
    // Midnight after 6 August in New York is 04:00 UTC on the 7th.
    expect(end.toISOString()).toBe('2026-08-07T03:59:59.999Z')
  })

  it('puts a calendar date on its own day and an instant on the tenant clock', () => {
    setDisplayTimezone('America/Los_Angeles')
    expect(dateToParam(toWallClockDate('2026-08-06'))).toBe('2026-08-06')
    // 05:00 UTC on the 7th is still 22:00 on the 6th in Los Angeles.
    const instant = toWallClockDate('2026-08-07T05:00:00Z')
    expect(dateToParam(instant)).toBe('2026-08-06')
    expect(instant.getHours()).toBe(22)
  })
})
