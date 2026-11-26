import { formatDateOrDash, formatDateTimeOrDash, toLocalDayStart } from '@/core/utils/dates'

import type { Schemas } from '@/core/api/generated'

export type RedatedOrder = Schemas['RedatedOrderResponse']
type Reason = Schemas['RedatedOrderReasonResponse']

export type RedatedShiftKind = 'earlier' | 'later' | 'dated' | 'undated'

export interface RedatedShift {
  kind: RedatedShiftKind
  // Whole local days between before and after, 0 for dated and undated.
  days: number
}

const DAY_MS = 24 * 60 * 60 * 1000

// The day in the display timezone, the one the backend diffs by.
function localDay(iso: string): number {
  return toLocalDayStart(iso).getTime()
}

// The walk lists an order once the day of its start or of its end changed,
// so the start counts when it moved and the end otherwise.
export function redatedShift(row: RedatedOrder): RedatedShift {
  const before = row.before_planned_start ?? row.before_planned_end
  const after = row.after_planned_start ?? row.after_planned_end
  if (!before) return { kind: 'dated', days: 0 }
  if (!after) return { kind: 'undated', days: 0 }
  let days = Math.round((localDay(after) - localDay(before)) / DAY_MS)
  if (days === 0 && row.before_planned_end && row.after_planned_end) {
    days = Math.round((localDay(row.after_planned_end) - localDay(row.before_planned_end)) / DAY_MS)
  }
  return { kind: days < 0 ? 'earlier' : 'later', days: Math.abs(days) }
}

export function shiftSeverity(row: RedatedOrder, shift: RedatedShift): string {
  if (row.reason?.kind === 'order_line' && row.reason.late) return 'danger'
  if (shift.kind === 'earlier') return 'success'
  if (shift.kind === 'later') return 'warn'
  if (shift.kind === 'dated') return 'info'
  return 'secondary'
}

// A wait in the unit a planner reads it in: whole hours, else minutes.
export function formatWait(minutes: number): string {
  return minutes >= 60 && minutes % 60 === 0 ? `${minutes / 60} h` : `${minutes} min`
}

export interface ReasonText {
  icon: string
  key: string
  params: Record<string, unknown>
  detailKey: string | null
  detailParams: Record<string, unknown>
}

const KEY = 'productionSchedule.autoPlan.redated.reason'

function text(
  icon: string,
  key: string,
  params: Record<string, unknown> = {},
  detailKey: string | null = null,
  detailParams: Record<string, unknown> = {},
): ReasonText {
  return { icon, key: `${KEY}.${key}`, params, detailKey: detailKey && `${KEY}.${detailKey}`, detailParams }
}

function orderRef(number: string | null, id: number | null): string {
  return number ?? (id !== null ? `#${id}` : '')
}

function pieces(processed: number | null, quantity: number | null) {
  const done = processed ?? 0
  const all = quantity ?? 0
  return { processed: done, quantity: all, left: Math.max(all - done, 0) }
}

// The reason of a re-dated order as an icon, a label and a detail line, the
// keys of the productionSchedule.autoPlan.redated.reason namespace.
export function redatedReasonText(reason: Reason | null | undefined): ReasonText {
  if (!reason) return text('mdi-refresh', 'walkedMeanwhile')
  const moment = formatDateTimeOrDash(reason.moment)
  const day = formatDateOrDash(reason.day)
  switch (reason.kind) {
    case 'ready_now':
      return text('mdi-check-circle-outline', 'readyNow', {}, 'readyNowDetail')
    case 'queue': {
      const order = orderRef(reason.previous_order_number, reason.previous_order_id)
      if (!reason.previous_running) {
        return text('mdi-arrow-right-bold-circle-outline', 'queue', { order }, 'queueDetail', { moment })
      }
      const counts = pieces(reason.previous_pieces_processed, reason.previous_quantity)
      return reason.previous_overrun
        ? text('mdi-progress-clock', 'queueRunning', { order }, 'queueOverrunDetail', { ...counts, moment })
        : text('mdi-progress-clock', 'queueRunning', { order }, 'queueDetail', { moment })
    }
    case 'predecessor': {
      const sequence = reason.predecessor_sequence ?? ''
      if (reason.wait_after_minutes > 0) {
        return text(
          'mdi-timer-sand',
          'waitAfter',
          { duration: formatWait(reason.wait_after_minutes) },
          'waitAfterDetail',
          { sequence, moment: reason.moment ? moment : day },
        )
      }
      const when = reason.moment ? moment : day
      return reason.predecessor_order_number
        ? text('mdi-arrow-right-bold-circle-outline', 'predecessor', { sequence }, 'predecessorDetail', {
            order: reason.predecessor_order_number,
            moment: when,
          })
        : text('mdi-arrow-right-bold-circle-outline', 'predecessor', { sequence }, 'predecessorReadyDetail', {
            sequence,
            moment: when,
          })
    }
    case 'order_line': {
      const params = { line: reason.order_item_id ?? '' }
      const detail = { date: formatDateOrDash(reason.expected_date), days: reason.response_time_days }
      if (reason.forecast) {
        return text('mdi-truck-fast-outline', 'orderLineForecast', params, 'orderLineForecastDetail', detail)
      }
      if (reason.late) {
        return text('mdi-truck-alert-outline', 'orderLineLate', params, 'orderLineLateDetail', detail)
      }
      return reason.arrived
        ? text('mdi-truck-check-outline', 'orderLine', params, 'orderLineArrivedDetail', detail)
        : text('mdi-truck-delivery-outline', 'orderLine', params, 'orderLineDetail', detail)
    }
    case 'raw_material':
      return text('mdi-package-variant', 'rawMaterial', {}, 'rawMaterialDetail', { date: day })
    case 'not_before':
      return text('mdi-calendar-start', 'notBefore', { date: day })
    case 'in_progress': {
      const counts = pieces(reason.pieces_processed, reason.quantity)
      return text('mdi-progress-clock', 'running', {}, reason.overrun ? 'runningOverrunDetail' : 'runningDetail', counts)
    }
    case 'pinned':
      return text('mdi-pin-outline', 'pinned')
    case 'frozen':
      return text('mdi-snowflake', 'frozen')
    case 'undated':
      return text('mdi-calendar-question', 'undated', {}, 'undatedDetail')
    default:
      return text('mdi-refresh', 'walkedMeanwhile')
  }
}
