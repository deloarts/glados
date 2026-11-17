import { ref } from 'vue'

import { getEmptyPlaceholder } from './emptyValue'
import { localeTag } from './dates'
import type { AppLocale } from '@/core/i18n'

/**
 * The currency prices are displayed in: the tenant's `general.currency`
 * setting (an ISO 4217 code like "EUR"), presentation-only. Prices are
 * always stored and sent as plain integer cents, this never converts them.
 *
 * A ref rather than a plain module variable so that templates calling
 * `formatPrice` re-render when the setting changes, mirroring `dates.ts`'s
 * `displayTimezone` pattern.
 *
 * '' (unset) falls back to 'EUR': the backend's own server_default/seed.
 */
const displayCurrency = ref('EUR')

export function setDisplayCurrency(currency: string | null): void {
  displayCurrency.value = currency || 'EUR'
}

export function getDisplayCurrency(): string {
  return displayCurrency.value
}

/**
 * Locale-aware currency string for a price stored in cents. Locale and
 * currency default to the UI's, but order mail passes the supplier's own.
 */
export function formatPrice(
  cents: number | null,
  locale?: AppLocale,
  currency = getDisplayCurrency(),
): string {
  if (cents === null) return getEmptyPlaceholder()
  return new Intl.NumberFormat(localeTag(locale), { style: 'currency', currency }).format(
    cents / 100,
  )
}

/**
 * The currency symbol plus a space for an `InputNumber` prefix, taken from
 * `formatToParts` so any currency renders its real symbol.
 */
export function currencyInputPrefix(currency = getDisplayCurrency()): string {
  const parts = new Intl.NumberFormat(localeTag(), { style: 'currency', currency }).formatToParts(
    0,
  )
  const symbol = parts.find((part) => part.type === 'currency')?.value ?? currency
  return `${symbol} `
}

/** Locale-aware percentage string for a 0-1 ratio. */
export function formatPercent(ratio: number | null, locale?: AppLocale): string {
  if (ratio === null) return getEmptyPlaceholder()
  return new Intl.NumberFormat(localeTag(locale), {
    style: 'percent',
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(ratio)
}
