import { API_MAX_PAGE_SIZE } from '@/core/constants/table'

import type { PageResponse } from '@/core/api/types'
import type { PageWindow } from '@/core/api/fetchAllPages'

/** Above this many rows an export asks before it starts, since it takes a while. */
export const EXPORT_CONFIRM_ROWS = 5_000

/**
 * The most rows one export reads. Past it the browser holds too much at once
 * and the export would take minutes, so the user narrows the filter instead.
 */
export const EXPORT_MAX_ROWS = 50_000

export interface FetchExportRowsOptions {
  signal: AbortSignal
  /** Called after every page with the rows read so far and the list's total. */
  onProgress?: (loaded: number, total: number) => void
  maxRows?: number
}

/**
 * Reads every row of a filtered list for an export, page by page at the
 * largest size the API accepts, until it holds the list's total, a page comes
 * back short or `maxRows` is reached. Unlike fetchAllPages it reports its
 * progress and stops when `signal` aborts, since an export may read a list
 * that grows with the business. The pages are read by offset, so a row
 * created or deleted while the export runs can shift one row across a page
 * boundary, which an office export accepts.
 */
export async function fetchExportRows<T>(
  fetchPage: (window: PageWindow, signal: AbortSignal) => Promise<PageResponse<T>>,
  options: FetchExportRowsOptions,
): Promise<T[]> {
  const { signal, onProgress, maxRows = EXPORT_MAX_ROWS } = options
  const items: T[] = []
  for (;;) {
    signal.throwIfAborted()
    const limit = Math.min(API_MAX_PAGE_SIZE, maxRows - items.length)
    const page = await fetchPage({ skip: items.length, limit }, signal)
    signal.throwIfAborted()
    items.push(...page.items)
    const total = Math.min(page.total, maxRows)
    onProgress?.(Math.min(items.length, total), total)
    if (page.items.length < limit || items.length >= total) return items.slice(0, maxRows)
  }
}
