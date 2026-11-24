import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { ExternalWorkQuery, ExternalWorkRow } from '../types/externalWork'

/** One page of the positions that go to a supplier for an outside process. */
export async function getExternalWork(
  params?: ExternalWorkQuery,
): Promise<PageResponse<ExternalWorkRow>> {
  return webApi.get('/external-work/', { query: params }) as Promise<PageResponse<ExternalWorkRow>>
}
