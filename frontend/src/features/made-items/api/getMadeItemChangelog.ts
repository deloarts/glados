import { getChangelog } from '@/shared/api/getChangelog'

import type { MadeItemChangelogEntry } from '../types/madeItemsChangelogResponse'

export async function getMadeItemChangelog(itemId: number): Promise<MadeItemChangelogEntry[]> {
  return getChangelog('/made-items/{item_id}/changelog', { path: { item_id: itemId } })
}
