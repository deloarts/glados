import { getChangelog } from '@/shared/api/getChangelog'

import type { SourceItemChangelogEntry } from '../types/sourceItemsChangelogResponse'

export async function getSourceItemChangelog(itemId: number): Promise<SourceItemChangelogEntry[]> {
  return getChangelog('/source-items/{item_id}/changelog', { path: { item_id: itemId } })
}
