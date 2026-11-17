import type { SequenceStatus, SequenceSummaryResponse } from '../types/sequence'

export function sequenceStatus(row: Pick<SequenceSummaryResponse, 'released_at' | 'superseded_at'>): SequenceStatus {
  if (row.superseded_at) return 'superseded'
  return row.released_at ? 'released' : 'draft'
}

export const STATUS_SEVERITY: Record<SequenceStatus, 'success' | 'secondary' | 'warn'> = {
  draft: 'warn',
  released: 'success',
  superseded: 'secondary',
}
