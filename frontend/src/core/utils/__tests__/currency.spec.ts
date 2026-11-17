import { describe, it, expect, afterEach } from 'vitest'

import {
  currencyInputPrefix,
  formatPercent,
  formatPrice,
  getDisplayCurrency,
  setDisplayCurrency,
} from '../currency'
import { i18n } from '@/core/i18n'

describe('formatPrice', () => {
  afterEach(() => {
    i18n.global.locale.value = 'enGB'
    // displayCurrency is module-level state (set once from /host/capabilities);
    // leaking it between cases would make these order-dependent.
    setDisplayCurrency(null)
  })

  it('returns the empty placeholder for null', () => {
    expect(formatPrice(null)).toBe('-')
  })

  it('formats cents as English currency by default', () => {
    expect(formatPrice(123456)).toBe('€1,234.56')
  })

  // Intl's de-AT output uses a non-breaking space (U+00A0) between the
  // symbol and the number, not a regular space; asserted on explicitly so
  // a future edit doesn't silently "normalize" it to a plain space.
  const DE_AT_1234_56 = '€ 1.234,56'

  it('formats using an explicit locale, ignoring the current UI locale', () => {
    i18n.global.locale.value = 'enGB'
    expect(formatPrice(123456, 'deAT')).toBe(DE_AT_1234_56)
  })

  it('follows the current UI locale when none is given explicitly', () => {
    i18n.global.locale.value = 'deAT'
    expect(formatPrice(123456)).toBe(DE_AT_1234_56)
  })

  it('formats zero correctly, not as falsy/empty', () => {
    expect(formatPrice(0)).toBe('€0.00')
  })

  it('supports a different currency', () => {
    // en-GB renders USD as "US$" to stay unambiguous next to "£".
    expect(formatPrice(500, 'enGB', 'USD')).toBe('US$5.00')
  })
})

describe('setDisplayCurrency / getDisplayCurrency', () => {
  afterEach(() => {
    setDisplayCurrency(null)
  })

  it('defaults to EUR before anything has set it', () => {
    expect(getDisplayCurrency()).toBe('EUR')
  })

  it('changes formatPrice\'s default currency once set', () => {
    setDisplayCurrency('USD')

    expect(getDisplayCurrency()).toBe('USD')
    expect(formatPrice(500, 'enGB')).toBe('US$5.00')
  })

  it('falls back to EUR for a null/empty value, mirroring setDisplayTimezone', () => {
    setDisplayCurrency('USD')
    setDisplayCurrency(null)

    expect(getDisplayCurrency()).toBe('EUR')
  })

  it('does not override an explicit currency argument', () => {
    setDisplayCurrency('USD')

    expect(formatPrice(500, 'enGB', 'GBP')).toBe('£5.00')
  })
})

describe('currencyInputPrefix', () => {
  afterEach(() => {
    setDisplayCurrency(null)
  })

  it('renders the EUR symbol plus a trailing space by default', () => {
    expect(currencyInputPrefix('EUR')).toBe('€ ')
  })

  it('renders the USD symbol plus a trailing space', () => {
    // en-GB renders USD as "US$" to stay unambiguous next to "£", same as
    // formatPrice's own USD case above.
    expect(currencyInputPrefix('USD')).toBe('US$ ')
  })

  it('follows the current display currency when none is given explicitly', () => {
    setDisplayCurrency('GBP')
    expect(currencyInputPrefix()).toBe('£ ')
  })
})

describe('formatPercent', () => {
  afterEach(() => {
    i18n.global.locale.value = 'enGB'
  })

  it('returns the empty placeholder for null', () => {
    expect(formatPercent(null)).toBe('-')
  })

  it('formats a 0-1 ratio as one-decimal English percent by default', () => {
    expect(formatPercent(0.123)).toBe('12.3%')
  })

  // Intl's de-AT output uses a non-breaking space (U+00A0) before the sign,
  // and a comma decimal separator; asserted on explicitly so a future edit
  // doesn't silently "normalize" it to a plain space/period.
  it('follows the current UI locale when none is given explicitly', () => {
    i18n.global.locale.value = 'deAT'
    expect(formatPercent(0.123)).toBe('12,3 %')
  })

  it('formats using an explicit locale, ignoring the current UI locale', () => {
    i18n.global.locale.value = 'enGB'
    expect(formatPercent(0.123, 'deAT')).toBe('12,3 %')
  })

  it('formats zero correctly, not as falsy/empty', () => {
    expect(formatPercent(0)).toBe('0.0%')
  })
})
