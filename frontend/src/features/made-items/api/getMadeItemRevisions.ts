import { webApi } from '@/core/api/webRequest'

import type { MadeItemRevisionsResponse } from '../types/madeItemsResponse'

/**
 * `GET /made-items/{id}/revisions`: every sibling sharing this item's
 * part number (newest first), plus what
 * creating a new revision from this specific item would look like
 * (`next_revision`/`next_revision_error`/`can_create`/`reason`). Readable by
 * anyone who can read the item; only `POST` requires `write:made_items`.
 */
export async function getMadeItemRevisions(itemId: number): Promise<MadeItemRevisionsResponse> {
  return webApi.get('/made-items/{item_id}/revisions', { path: { item_id: itemId } })
}
