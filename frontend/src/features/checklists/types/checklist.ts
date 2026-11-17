import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type ChecklistResponse = Schemas['ChecklistResponse']
export type ChecklistSummaryResponse = Schemas['ChecklistSummaryResponse']
export type ChecklistCreateRequest = Schemas['ChecklistCreateRequest']
export type ChecklistUpdateRequest = Schemas['ChecklistUpdateRequest']
export type ChecklistVerdict = ChecklistSummaryResponse['verdict']

/** Who a checklist belongs to. Neither project nor product means personal. */
export type ChecklistOwner =
  | { kind: 'personal' }
  | { kind: 'project'; id: number; label: string }
  | { kind: 'product'; id: number; label: string }

export type ChecklistListParams = QueryOf<'/checklists'>

/** Fields the checklist list can be sorted by on the server. */
export type ChecklistSortBy = NonNullable<ChecklistListParams['order_by']>

/**
 * Where a checklist stands: a draft is being filled in, released is signed
 * off, done is a finished checklist of a type without a release, and
 * superseded is a revision a newer one has replaced.
 */
export type ChecklistStatus = 'draft' | 'done' | 'released' | 'superseded'
