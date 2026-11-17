/** What a report prints in place of a missing value. */
export const REPORT_EMPTY = '–'

/** The text, or `REPORT_EMPTY` when it is missing or only whitespace. */
export function orDash(value: string | null | undefined): string {
  return value && value.trim() !== '' ? value : REPORT_EMPTY
}
