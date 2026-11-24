import type { WidgetDataOf } from '../types/infoscreenFeed'
import { daysBetween } from './infoscreenFormat'

export type ExternalWorkRow = WidgetDataOf<'external_work'>['rows'][number]

/** The line above the rows: what goes out today, this week, and how much is critical. */
export interface ExternalWorkSummary {
  // Due today or overdue.
  today: number
  // Due within the next seven days, today and overdue ones included.
  week: number
  critical: number
}

export function summarizeExternalWork(rows: ExternalWorkRow[], todayKey: string): ExternalWorkSummary {
  const offsets = rows.map((row) =>
    row.latest_pickup_date ? daysBetween(todayKey, row.latest_pickup_date) : null,
  )
  return {
    today: offsets.filter((offset) => offset !== null && offset <= 0).length,
    week: offsets.filter((offset) => offset !== null && offset <= 6).length,
    critical: rows.filter((row) => row.alert !== null).length,
  }
}

export interface ExternalWorkDayGroup {
  key: string
  kind: 'overdue' | 'today' | 'tomorrow' | 'later'
  // The day of a later group, for its weekday heading.
  date: string | null
  rows: ExternalWorkRow[]
}

/**
 * The rows by the day they must leave at the latest, in the feed's order:
 * the overdue ones first, then today, tomorrow and the later days. The day
 * is the display's own, so the groups follow the clock between feeds.
 */
export function groupExternalWorkByDay(
  rows: ExternalWorkRow[],
  todayKey: string,
): ExternalWorkDayGroup[] {
  const groups: ExternalWorkDayGroup[] = []
  for (const row of rows) {
    const offset = row.latest_pickup_date ? daysBetween(todayKey, row.latest_pickup_date) : 0
    const kind: ExternalWorkDayGroup['kind'] =
      offset < 0 ? 'overdue' : offset === 0 ? 'today' : offset === 1 ? 'tomorrow' : 'later'
    const key = kind === 'later' ? (row.latest_pickup_date ?? 'later') : kind
    const last = groups[groups.length - 1]
    if (last && last.key === key) last.rows.push(row)
    else groups.push({ key, kind, date: kind === 'later' ? row.latest_pickup_date : null, rows: [row] })
  }
  return groups
}

export interface ExternalWorkLane {
  // The supplier, or null for parts nobody suggests a supplier for.
  supplier: string | null
  // Every part of the lane only has the supplier as a suggestion.
  suggested: boolean
  nextLatestPickup: string | null
  ready: number
  critical: number
  rows: ExternalWorkRow[]
}

/**
 * One lane per supplier, the line's or the suggested one, for collecting a
 * batch: the next day a part of it must leave and how many of its parts
 * are there already. Lanes come in the order of their next send-out day.
 */
export function groupExternalWorkBySupplier(rows: ExternalWorkRow[]): ExternalWorkLane[] {
  const lanes = new Map<string, ExternalWorkLane>()
  for (const row of rows) {
    const key = row.supplier_name ?? ''
    const lane = lanes.get(key) ?? {
      supplier: row.supplier_name,
      suggested: true,
      nextLatestPickup: null,
      ready: 0,
      critical: 0,
      rows: [],
    }
    lane.rows.push(row)
    lane.suggested = lane.suggested && row.supplier_suggested
    if (row.ready_now) lane.ready += 1
    if (row.alert !== null) lane.critical += 1
    if (row.latest_pickup_date && (!lane.nextLatestPickup || row.latest_pickup_date < lane.nextLatestPickup)) {
      lane.nextLatestPickup = row.latest_pickup_date
    }
    lanes.set(key, lane)
  }
  return [...lanes.values()].sort((a, b) =>
    (a.nextLatestPickup ?? '9999').localeCompare(b.nextLatestPickup ?? '9999'),
  )
}
