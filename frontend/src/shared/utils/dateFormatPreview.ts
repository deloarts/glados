import { formatISODateAs, formatISODateTimeAs, formatTimeInZone } from '@/core/utils/dates'
import type { DateFormatPreset } from '@/core/utils/dates'

/**
 * Sample values for the settings screens that let a user or an admin pick a
 * date format and a timezone, so both pickers label and preview their
 * choices the same way.
 */

/** Day 6 and month 8 make day-month versus month-day order obvious. */
export const DATE_FORMAT_SAMPLE = '2026-08-06T14:32:00+00:00'

/**
 * The server's presets as Select options, each labelled by its own rendering
 * of the sample. The preset is passed explicitly, since reading the live
 * preference inside a computed that writes it would be a recursive update.
 */
export function dateFormatSelectOptions(
  presets: readonly string[],
): { value: string; label: string }[] {
  return presets.map((preset) => ({
    value: preset,
    label: formatISODateAs(DATE_FORMAT_SAMPLE, preset as DateFormatPreset),
  }))
}

/**
 * The sample rendered in one preset, with the 24-hour time when `withTime`
 * is set. Empty when no preset is selected.
 */
export function dateFormatSample(preset: string | null | undefined, withTime = false): string {
  if (!preset) return ''
  const format = withTime ? formatISODateTimeAs : formatISODateAs
  return format(DATE_FORMAT_SAMPLE, preset as DateFormatPreset)
}

/**
 * The current 24-hour time in a timezone, to verify the choice. Fixed en-GB
 * formatting rather than the viewer's preferences, since the value may apply
 * to other users. Empty when no zone is selected or the browser does not know
 * it, so an unknown zone shows nothing rather than breaking the page.
 */
export function timezoneNowPreview(timeZone: string | null | undefined): string {
  if (!timeZone) return ''
  try {
    return formatTimeInZone(new Date(), timeZone)
  } catch {
    return ''
  }
}
