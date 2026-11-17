import type { PublicUser } from '@/core/types/userResponse'
import type { LocalizedText } from '@/shared/utils/localizedText'
import type { ListPlaceTarget } from '@/shared/types/listOrder'

/**
 * A name or description: a language map for the localized catalogue labels
 * (article groups, source item types), one string for the rest (product
 * families).
 */
export type NamedText = LocalizedText | string

/**
 * The shape shared by the simplest catalogue "type" resources: a named,
 * colour-labelled, archivable record with an optional description and a
 * creator. SimpleNamedEntityFormDialog
 * and SimpleNamedEntityManagementTable are generic over this shape, so any
 * store/response pair that already matches it can drop in without a cast.
 */
// eslint-disable-next-line no-restricted-syntax -- a structural constraint the simple master-data responses must satisfy
export interface SimpleNamedEntity {
  id: number
  public_id: string
  created: string
  changed: string
  archived: boolean
  name: NamedText
  label_color: string
  label_font_color: string
  description: NamedText
  creator_id: number
  creator: PublicUser | null
  changed_by: PublicUser | null
}

export interface SimpleNamedEntityCreatePayload<TText extends NamedText> {
  name: TText
  description?: TText
  label_color?: string
  label_font_color?: string
}

// A PUT replaces the whole record, so the name is always sent.
export interface SimpleNamedEntityUpdatePayload<TText extends NamedText> {
  name: TText
  description?: TText | null
  label_color?: string | null
  label_font_color?: string | null
}

/** The store surface SimpleNamedEntityFormDialog needs to save a create or edit. */
export interface SimpleNamedEntityFormStore<T, TText extends NamedText> {
  create: (payload: SimpleNamedEntityCreatePayload<TText>) => Promise<T>
  update: (id: number, payload: SimpleNamedEntityUpdatePayload<TText>) => Promise<T>
}

/**
 * A store of either kind; the dialog and table send the payload their
 * `localized` prop says.
 */
export type AnyNamedEntityFormStore<T> =
  | SimpleNamedEntityFormStore<T, string>
  | SimpleNamedEntityFormStore<T, LocalizedText>

/**
 * The store surface SimpleNamedEntityManagementTable needs, on top of the
 * create/update pair above: the paginated table state, the archive/restore
 * pair used instead of a hard delete and the place a dragged row takes
 * within the hand-kept order.
 */
export interface SimpleNamedEntityManagementStore<
  T,
  TSortBy extends string,
  TText extends NamedText = NamedText,
> extends SimpleNamedEntityFormStore<T, TText> {
  tableItems: T[]
  total: number
  loading: boolean
  search: string
  sortBy: TSortBy | null
  sortDir: 'asc' | 'desc'
  showArchived: boolean
  showActions: boolean
  clearTrigger: number
  refreshTrigger: number
  refreshTable: (page?: { skip: number; limit: number }) => Promise<void>
  setSort: (field: TSortBy, dir: 'asc' | 'desc') => void
  clearSort: () => void
  archive: (id: number) => Promise<void>
  restore: (id: number) => Promise<void>
  /** Whether the table shows the hand-kept order, so rows can be dragged. */
  manualOrder: boolean
  place: (id: number, target: ListPlaceTarget, droppedPage?: T[]) => Promise<void>
}

export type AnyNamedEntityManagementStore<T, TSortBy extends string> =
  | SimpleNamedEntityManagementStore<T, TSortBy, string>
  | SimpleNamedEntityManagementStore<T, TSortBy, LocalizedText>
