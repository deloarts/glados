import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'

// Grouping stays off: these values are already scaled down to a small
// number (never more than four digits before the unit threshold moves to
// the next one), so there is nothing useful to group, only the decimal
// separator needs to follow the active UI language.
const SCALED_VALUE_OPTIONS: Intl.NumberFormatOptions = {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  useGrouping: false,
}

/**
 * Human-readable file size for UI display (file lists, upload popovers).
 *
 * Binary (1024-based) units written without the "i" (KB and MB rather than
 * KiB and MiB). The result is a compact size for a table or popover cell,
 * not a byte-precise one.
 *
 * `useLocaleFormat` reads the active UI locale internally rather than
 * requiring a component setup context, so it is safe to call from this
 * plain utility function too, see its own docstring.
 */
export function formatBytes(bytes: number): string {
  const { formatNumber } = useLocaleFormat()
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${formatNumber(bytes / 1024, SCALED_VALUE_OPTIONS)} KB`
  return `${formatNumber(bytes / (1024 * 1024), SCALED_VALUE_OPTIONS)} MB`
}
