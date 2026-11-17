import type { AppLocale } from '@/core/i18n'
import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { roundTo, withoutNegativeZero } from '@/core/utils/numbers'

/**
 * Number formatting of the drive sizing in the UI language, or in `locale`
 * for a report exported in another language. Values are rounded before
 * formatting, so a tiny negative remainder never shows as "-0.00".
 */
export function useDriveSizingFormat(locale?: AppLocale) {
  const { formatNumber } = useLocaleFormat(locale)

  function settle(value: number, digits: number): number {
    return withoutNegativeZero(roundTo(value, digits))
  }

  function fixed(value: number, digits: number): string {
    return formatNumber(settle(value, digits), {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    })
  }

  function num(value: number, digits = 3): string {
    return formatNumber(settle(value, digits), { maximumFractionDigits: digits })
  }

  function percent(fraction: number): string {
    return formatNumber(settle(fraction, 2), { style: 'percent', maximumFractionDigits: 0 })
  }

  return { fixed, num, percent }
}
