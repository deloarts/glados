import type {
  LotPositionKind,
  LotPositionStatus,
  LotPriority,
  LotStatus,
} from '../types/productionLotsResponse'
import type { StepDisplayStatus } from '../types/productionLotsRequest'

export const LOT_STATUSES: LotStatus[] = [
  'draft',
  'partially_planned',
  'planned',
  'in_progress',
  'on_hold',
  'completed',
  'canceled',
  'scrapped',
]

export const lotStatusSeverity: Record<LotStatus, string> = {
  draft: 'secondary',
  partially_planned: 'info',
  planned: 'info',
  in_progress: 'warn',
  on_hold: 'danger',
  completed: 'success',
  canceled: 'danger',
  scrapped: 'danger',
}

// Completed, canceled and scrapped lots accept no further edits.
export function isTerminalLotStatus(status: LotStatus): boolean {
  return status === 'completed' || status === 'canceled' || status === 'scrapped'
}

export const LOT_PRIORITIES: LotPriority[] = ['low', 'normal', 'high', 'critical']

export const lotPrioritySeverity: Record<LotPriority, string> = {
  low: 'secondary',
  normal: 'info',
  high: 'warn',
  critical: 'danger',
}

export const lotPositionStatusSeverity: Record<LotPositionStatus, string> = {
  pending: 'secondary',
  ordered_or_queued: 'info',
  in_progress: 'warn',
  partially_completed: 'warn',
  completed: 'success',
  canceled: 'danger',
}

export const lotPositionKindSeverity: Record<LotPositionKind, string> = {
  unassigned: 'secondary',
  external: 'info',
  internal: 'help',
  mixed: 'contrast',
}

// Refines ORDERED_OR_QUEUED and PENDING by position kind. An internal
// position is only queued and an external one only ordered. An external or
// mixed position exists only once an order item covers it, so PENDING there
// means the buyer has not placed the order yet. Returns the leaf i18n key.
export function lotPositionStatusKey(
  status: LotPositionStatus,
  kind: LotPositionKind | null | undefined,
): string {
  if (status === 'pending') {
    return kind === 'external' || kind === 'mixed' ? 'allocated' : status
  }
  if (status !== 'ordered_or_queued') return status
  if (kind === 'internal') return 'queued'
  if (kind === 'external') return 'ordered'
  return status
}

// Every key lotPositionStatusKey can produce, in filter order.
export const STEP_DISPLAY_STATUSES: StepDisplayStatus[] = [
  'pending',
  'allocated',
  'ordered',
  'queued',
  'ordered_or_queued',
  'in_progress',
  'partially_completed',
  'completed',
  'canceled',
]

// Severity per display key, falling back to the stored-status map.
const DISPLAY_STATUS_SEVERITY: Record<string, string> = {
  // Matches the allocated tag in the demand tables.
  allocated: 'warn',
  ordered: 'info',
  queued: 'info',
}

export function lotPositionStatusSeverityFor(
  status: LotPositionStatus,
  kind: LotPositionKind | null | undefined,
): string {
  const key = lotPositionStatusKey(status, kind)
  return DISPLAY_STATUS_SEVERITY[key] ?? lotPositionStatusSeverity[status]
}
