import type { TagSeverity } from '@/core/types/tagSeverity'
import type {
  QuoteRequestLineResponse,
  QuoteRequestLineState,
  QuoteRequestResponse,
  QuoteRequestStatus,
} from '../types/quoteRequestsResponse'

const STATUS_SEVERITY: Record<QuoteRequestStatus, TagSeverity> = {
  draft: 'warn',
  sent: 'info',
  awarded: 'success',
  closed: 'secondary',
  canceled: 'danger',
}

const LINE_STATE_SEVERITY: Record<QuoteRequestLineState, TagSeverity> = {
  open: 'info',
  awarded: 'success',
  dropped: 'secondary',
}

export function quoteRequestStatusSeverity(status: QuoteRequestStatus): TagSeverity {
  return STATUS_SEVERITY[status]
}

export function quoteLineStateSeverity(state: QuoteRequestLineState): TagSeverity {
  return LINE_STATE_SEVERITY[state]
}

/** Whether lines, suppliers and offers of the request may change. */
export function isQuoteRequestOpen(request: Pick<QuoteRequestResponse, 'status'>): boolean {
  return request.status === 'draft' || request.status === 'sent'
}

/**
 * Whether a dropped line may be taken back: while the request is open, and
 * while it is closed or awarded only because every line was decided, as the
 * backend rules have it. A recorded close holds until the request is
 * reopened.
 */
export function linesRestorable(
  request: Pick<QuoteRequestResponse, 'status' | 'closed_at'>,
): boolean {
  return (
    isQuoteRequestOpen(request) ||
    ((request.status === 'closed' || request.status === 'awarded') && request.closed_at === null)
  )
}

/**
 * Whether the request offers Reopen by its state: someone closed it and an
 * award on it was voided since, which left that line open, as the backend
 * rules have it. A canceled request is never reopened.
 */
export function reopenOffered(
  request: Pick<QuoteRequestResponse, 'status' | 'closed_at' | 'lines'>,
): boolean {
  return (
    request.status === 'closed' &&
    request.closed_at !== null &&
    request.lines.some((line) => line.award_voided && line.state === 'open')
  )
}

/** The statuses the Manage Quotes panels offer requests in. */
export const OPEN_QUOTE_REQUEST_STATUSES = ['draft', 'sent'] as const satisfies readonly QuoteRequestStatus[]

/**
 * The catalogue a substitute for the line comes from, or null when the line
 * takes none: a lot position or free-text line names no catalogue item, and
 * a bought line for a source item demand stays on its item, as the backend
 * rules have it.
 */
export function substituteKind(
  line: Pick<QuoteRequestLineResponse, 'line_type' | 'demands'>,
): 'BOUGHT' | 'SOURCE' | null {
  if (line.line_type === 'SOURCE') return 'SOURCE'
  if (line.line_type !== 'BOUGHT') return null
  return line.demands.some((d) => d.family === 'source') ? null : 'BOUGHT'
}
