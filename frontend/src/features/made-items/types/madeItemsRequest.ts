import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type MadeItemFilterParams = QueryOf<'/made-items'>
export type MadeItemSortBy = NonNullable<MadeItemFilterParams['order_by']>
export type MadeItemSortDir = NonNullable<MadeItemFilterParams['order_dir']>

export type MadeItemDataSource = Schemas['DataSource']

// role defaults to 'fabrication' on the backend.
export type MadeItemProcessCreateRequest = Omit<
  Schemas['MadeItemProcessCreateRequest'],
  'role'
> & {
  role?: Schemas['StepRole']
}

export type MadeItemProcessUpdateRequest = Omit<
  Schemas['MadeItemProcessUpdateRequest'],
  'role'
> & {
  role?: Schemas['StepRole']
}

export type MadeItemProcessReorderRequest = Schemas['MadeItemProcessReorderRequest']

export type MadeItemProcessRegroupRequest = Schemas['MadeItemProcessRegroupRequest']

// processes uses the request type with an optional role.
export type MadeItemCreateRequest = Omit<Schemas['MadeItemCreateRequest'], 'processes'> & {
  processes?: MadeItemProcessCreateRequest[]
}

// Revision is immutable; it changes only through a new revision.
export type MadeItemUpdateRequest = Schemas['MadeItemUpdateRequest']

/** 'ask' is resolved by the form; the payload carries a concrete status. */
export type RevisionPredecessorStatus = Schemas['MadeItemCreateRevisionRequest']['predecessor_status']

/**
 * The server fills in revision, part number and data source; a new
 * revision is born WEB and active with no successor and no files.
 */
export type MadeItemRevisionItemRequest = Omit<
  Schemas['MadeItemRevisionItemRequest'],
  'processes'
> & {
  processes?: MadeItemProcessCreateRequest[]
}

export type MadeItemCreateRevisionRequest = Omit<
  Schemas['MadeItemCreateRevisionRequest'],
  'item'
> & {
  item: MadeItemRevisionItemRequest
}
