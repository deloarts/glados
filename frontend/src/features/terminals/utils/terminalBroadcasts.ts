import { instantToPickerDate } from '@/core/utils/dates'

import type {
  TerminalBroadcastAudienceRequest,
  TerminalBroadcastResponse,
  TerminalBroadcastSeverity,
} from '../types/terminalResponse'

/** The server keeps a message to this many characters. */
export const BROADCAST_TEXT_MAX_LENGTH = 2000

/** How far ahead a message may run. */
export const BROADCAST_MAX_DAYS = 30

/** Who a new message reaches: every terminal, or a pick of terminals, of infoscreens or of both. */
export type BroadcastAudienceMode = 'all' | 'terminals' | 'infoscreens' | 'both'

/** The quick picks next to the date picker of "show until". */
export type BroadcastQuickPick = 'quarterHour' | 'hour' | 'endOfDay'

/**
 * The audience as the server takes it. A pick sends only the lists its mode
 * uses, so switching from both to terminals drops the infoscreens picked
 * before.
 */
export function audienceRequest(
  mode: BroadcastAudienceMode,
  terminalIds: number[],
  infoscreenIds: number[],
): TerminalBroadcastAudienceRequest {
  if (mode === 'all') return { all_terminals: true }
  return {
    all_terminals: false,
    terminal_ids: mode === 'terminals' || mode === 'both' ? [...terminalIds] : [],
    infoscreen_ids: mode === 'infoscreens' || mode === 'both' ? [...infoscreenIds] : [],
  }
}

/**
 * The picker value of a quick pick, on the tenant's wall clock like every
 * date picker in the app. The end of the day is one minute before midnight,
 * so the message is gone when the next day starts.
 */
export function quickPickUntil(pick: BroadcastQuickPick, now: Date): Date {
  if (pick === 'quarterHour') return roundToMinute(instantToPickerDate(new Date(now.getTime() + 15 * 60_000)))
  if (pick === 'hour') return roundToMinute(instantToPickerDate(new Date(now.getTime() + 60 * 60_000)))
  const endOfDay = instantToPickerDate(now)
  endOfDay.setHours(23, 59, 0, 0)
  return endOfDay
}

function roundToMinute(date: Date): Date {
  const rounded = new Date(date)
  rounded.setSeconds(0, 0)
  return rounded
}

/** The tag colour of a message's severity. */
export function broadcastTagSeverity(severity: TerminalBroadcastSeverity): 'info' | 'warn' | 'danger' {
  if (severity === 'warning') return 'warn'
  return severity
}

/** The messages still shown at `now`; a list loaded earlier can outlive a message's end. */
export function activeBroadcasts(
  broadcasts: TerminalBroadcastResponse[],
  now: number,
): TerminalBroadcastResponse[] {
  return broadcasts.filter(
    (broadcast) => broadcast.ended_at === null && Date.parse(broadcast.show_until) > now,
  )
}
