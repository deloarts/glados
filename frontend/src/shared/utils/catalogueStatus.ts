import type { TagSeverity } from '@/core/types/tagSeverity'

/**
 * Tag severity for the shared active, inactive and replaced catalogue status.
 */
export const catalogueStatusSeverity: Record<string, TagSeverity> = {
  active: 'success',
  replaced: 'warn',
  inactive: 'danger',
}

/** The catalogue status severity, with any unknown status shown as inactive. */
export function catalogueStatusTagSeverity(status: string): TagSeverity {
  return catalogueStatusSeverity[status] ?? 'danger'
}

/**
 * Severity of the PDM sync state, see docs/FIELD_OWNERSHIP.md. A conflict
 * is a parked ingest waiting in the admin pending list.
 */
export function pdmSyncStateSeverity(state: string): 'success' | 'warn' | 'danger' {
  if (state === 'synced') return 'success'
  if (state === 'missing') return 'warn'
  return 'danger'
}
