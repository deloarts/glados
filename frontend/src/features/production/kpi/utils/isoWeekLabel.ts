// Turns the backend's "YYYY-Www" iso_week key (see kpi_rules.py's
// _iso_week_key) into a compact chart-axis label, e.g. "W7" or "KW7"
// depending on the caller's locale-specific prefix.

/** The week number out of a "YYYY-Www" key, 0 if the string is malformed. */
export function isoWeekNumber(isoWeek: string): number {
  const match = /-W(\d{2})$/.exec(isoWeek)
  return match ? Number(match[1]) : 0
}

/** `prefix` is already resolved by the caller (e.g. t('productionKpi.weekPrefix')). */
export function formatIsoWeekLabel(isoWeek: string, prefix: string): string {
  return `${prefix}${isoWeekNumber(isoWeek)}`
}
