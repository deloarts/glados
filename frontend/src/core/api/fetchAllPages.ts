import { API_MAX_PAGE_SIZE } from '@/core/constants/table'

import type { PageResponse } from './types'

export interface PageWindow {
  skip: number
  limit: number
}

/**
 * Fetches every item of a paginated list by requesting consecutive skip and
 * limit windows until it holds `total` items, for views that need the whole
 * list rather than one page of it. The page size is capped at the largest
 * limit the API accepts, so a larger value never earns a 422. A page shorter
 * than the limit is the last one, which also ends the loop when `total`
 * shrinks while the pages are being read.
 */
export async function fetchAllPages<T>(
  fetchPage: (window: PageWindow) => Promise<PageResponse<T>>,
  pageSize: number = API_MAX_PAGE_SIZE,
): Promise<T[]> {
  const limit = Math.max(1, Math.min(pageSize, API_MAX_PAGE_SIZE))
  const items: T[] = []
  for (;;) {
    const page = await fetchPage({ skip: items.length, limit })
    items.push(...page.items)
    if (page.items.length < limit || items.length >= page.total) return items
  }
}
