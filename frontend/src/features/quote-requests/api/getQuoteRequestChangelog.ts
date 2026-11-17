import { getChangelog } from '@/shared/api/getChangelog'

import type { ChangelogEntry } from '@/shared/utils/changelog'

export async function getQuoteRequestChangelog(id: number): Promise<ChangelogEntry[]> {
  return getChangelog('/quote-requests/{request_id}/changelog', { path: { request_id: id } })
}
