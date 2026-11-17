import type { TagSeverity } from '@/core/types/tagSeverity'

import type { PdmSyncEntryAction, PdmSyncRunEntry } from '../types/adminSettingsTypes'

/**
 * Tag colour of a sync run entry's action, shared by the sync log and the
 * sync activity dialog.
 */
export function pdmEntryActionSeverity(action: PdmSyncEntryAction): TagSeverity {
  if (action === 'skipped') return 'secondary'
  if (action === 'missing' || action === 'thumbnail_error') return 'warn'
  if (action === 'conflict' || action === 'error' || action === 'writeback_error' || action === 'document_error') {
    return 'danger'
  }
  if (action === 'thumbnail') return 'info'
  return 'success' // created | revised | updated | claimed | status | writeback | document
}

/**
 * The catalogue page of the item an entry names. Only made and bought
 * entries can tell which catalogue that is; a document entry's own kind is
 * "document", so it gets no link rather than a wrong one.
 */
export function pdmEntryItemRoute(entry: PdmSyncRunEntry): string | null {
  if (entry.item_id === null) return null
  if (entry.kind === 'made') return `/catalogue/made-items/${entry.item_id}`
  if (entry.kind === 'bought') return `/catalogue/bought-items/${entry.item_id}`
  return null
}
