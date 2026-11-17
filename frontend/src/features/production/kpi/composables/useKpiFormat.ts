import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

const ONE_DECIMAL: Intl.NumberFormatOptions = { minimumFractionDigits: 1, maximumFractionDigits: 1 }
const UP_TO_TWO_DECIMALS: Intl.NumberFormatOptions = { minimumFractionDigits: 0, maximumFractionDigits: 2 }

/**
 * The number formats the KPI page and its panels share. A ratio shows as a
 * percentage with one decimal and the sign right after the number ("12,3%"),
 * a quantity with up to two decimals, and a number of days with one decimal.
 * A missing ratio or day count shows the empty placeholder.
 */
export function useKpiFormat() {
  const { formatNumber } = useLocaleFormat()

  /** A ratio from 0 to 1 as a percentage. */
  function formatPercent(value: number | null): string {
    if (value === null) return getEmptyPlaceholder()
    return `${formatNumber(value * 100, ONE_DECIMAL)}%`
  }

  function formatQuantity(value: number): string {
    return formatNumber(value, UP_TO_TWO_DECIMALS)
  }

  /** A number of days, without the unit. */
  function formatDays(value: number | null): string {
    if (value === null) return getEmptyPlaceholder()
    return formatNumber(value, ONE_DECIMAL)
  }

  return { formatPercent, formatQuantity, formatDays }
}
