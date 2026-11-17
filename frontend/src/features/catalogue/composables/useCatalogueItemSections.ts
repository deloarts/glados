import { reactive } from 'vue'

import type { SectionState } from '../types/itemDetail'

/**
 * A fresh, empty SectionState that can be bound straight into a card's
 * props. empty is the rest value, [] for a list or null for a single value.
 */
export function createSection<T>(empty: T): SectionState<T> {
  return reactive({ data: empty, loading: false, error: false, truncated: false }) as SectionState<T>
}

/**
 * Runs one section's loader and writes the result into section. An error
 * leaves data as it was, so one failing section never blanks the page.
 *
 * loader may resolve a bare value or an { items, total } page. opts.limit
 * flags the section as truncated when the list reaches it. opts.quiet skips
 * the loading flag for background refetches. opts.isCurrent re-checks the
 * caller's captured id after the loader settles; a stale call writes
 * nothing and leaves loading to the current one.
 */
export async function runSection<T>(
  section: SectionState<T>,
  loader: () => Promise<{ items: T; total?: number } | T>,
  opts?: { limit?: number; quiet?: boolean; isCurrent?: () => boolean },
): Promise<void> {
  const quiet = opts?.quiet ?? false
  if (!quiet) section.loading = true
  let failed = false
  let result: { items: T; total?: number } | T | undefined
  try {
    result = await loader()
  } catch {
    failed = true
  }

  const isCurrent = opts?.isCurrent ? opts.isCurrent() : true
  if (isCurrent) {
    if (failed) {
      section.error = true
    } else {
      const items = isItemsEnvelope(result as { items: T; total?: number } | T)
        ? (result as { items: T; total?: number }).items
        : (result as T)
      section.data = items
      section.truncated =
        opts?.limit !== undefined && Array.isArray(items) && items.length >= opts.limit
      section.error = false
    }
  }
  if (!quiet && isCurrent) section.loading = false
}

function isItemsEnvelope<T>(value: { items: T; total?: number } | T): value is { items: T; total?: number } {
  return typeof value === 'object' && value !== null && 'items' in value
}
