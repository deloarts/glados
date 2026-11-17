import { getChangelog } from '@/shared/api/getChangelog'

import type { BoughtItemChangelogEntry } from '../types/boughtItemsChangelogResponse'

export async function getBoughtItemChangelog(itemId: number): Promise<BoughtItemChangelogEntry[]> {
  return getChangelog('/bought-items/{item_id}/changelog', { path: { item_id: itemId } })
}
