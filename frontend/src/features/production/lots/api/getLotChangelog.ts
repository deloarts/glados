import { webApi } from '@/core/api/webRequest'

export async function getLotChangelog(id: number): Promise<string[]> {
  return webApi.get('/production-lots/{lot_id}/changelog', { path: { lot_id: id } })
}
