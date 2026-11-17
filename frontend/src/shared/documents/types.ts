/**
 * The document control fields every controlled document response carries,
 * such as a calculation or a checklist: its revision, release, invalid
 * marking and edit lock. The backend keeps the rules; these are read only.
 */
// eslint-disable-next-line no-restricted-syntax -- a structural constraint every controlled document response must satisfy
export interface ControlledDocument {
  id: number
  /** Shared by every revision of the document, such as "CAL-26-0042". */
  document_number: string
  revision: string
  is_latest: boolean
  superseded_at: string | null
  read_only: boolean
  released_at: string | null
  released_by_full_name: string | null
  invalid_at: string | null
  invalid_by_full_name: string | null
  invalid_reason: string | null
  /** Who edits the document right now; null once the lock has run out. */
  locked_by_id: number | null
  locked_by_full_name: string | null
  locked_at: string | null
  /** When the lease of the lock runs out unless it is renewed. */
  lock_expires_at: string | null
}
