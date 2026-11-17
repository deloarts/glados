import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'

/**
 * Formats fit calculator values in the UI language. Deviations are kept in µm
 * internally and shown signed in µm and mm; limit sizes and clearances in mm.
 */
export function useFitFormat() {
  const { formatNumber } = useLocaleFormat()

  const MM: Intl.NumberFormatOptions = { minimumFractionDigits: 3, maximumFractionDigits: 4 }

  function deviationUm(value: number): string {
    return `${formatNumber(value, { signDisplay: 'exceptZero', maximumFractionDigits: 2 })} µm`
  }

  function deviationMm(value: number): string {
    return `${formatNumber(value / 1000, { ...MM, signDisplay: 'exceptZero' })} mm`
  }

  function amountUm(value: number): string {
    return `${formatNumber(value, { maximumFractionDigits: 2 })} µm`
  }

  function amountMm(value: number): string {
    return `${formatNumber(value / 1000, MM)} mm`
  }

  function limitSize(size: number, deviation: number): string {
    return `${formatNumber(size + deviation / 1000, MM)} mm`
  }

  function nominal(size: number): string {
    return formatNumber(size, { maximumFractionDigits: 3 })
  }

  return { deviationUm, deviationMm, amountUm, amountMm, limitSize, nominal }
}
