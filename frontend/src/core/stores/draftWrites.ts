import { safeStorage } from '@/core/utils/safeStorage'

/**
 * Debounced localStorage writes for the persisted import drafts. A draft
 * store deep-watches a whole spreadsheet, so serialising it on every edit
 * would stringify every row per keystroke; instead the latest snapshot is
 * written once the draft has been still for DRAFT_WRITE_MS. A write that
 * hits a full or blocked storage is lost, which only costs the draft its
 * survival across a reload.
 *
 * Pending writes are kept per storage key, so a discarded draft or a logout
 * can cancel one before it lands, and they are flushed when the page is
 * hidden, so a reload right after an edit keeps it.
 */

export const DRAFT_WRITE_MS = 250

const pending = new Map<string, { timer: ReturnType<typeof setTimeout>; snapshot: () => unknown }>()

function write(key: string, snapshot: () => unknown): void {
  safeStorage.set(key, JSON.stringify(snapshot()))
}

/** Writes `snapshot()` under `key` once no further write was scheduled for it for DRAFT_WRITE_MS. */
export function scheduleDraftWrite(key: string, snapshot: () => unknown): void {
  cancelDraftWrite(key)
  const timer = setTimeout(() => {
    pending.delete(key)
    write(key, snapshot)
  }, DRAFT_WRITE_MS)
  pending.set(key, { timer, snapshot })
}

export function cancelDraftWrite(key: string): void {
  const entry = pending.get(key)
  if (!entry) return
  clearTimeout(entry.timer)
  pending.delete(key)
}

/** Writes every pending draft now. */
export function flushDraftWrites(): void {
  const entries = [...pending]
  pending.clear()
  for (const [key, { timer, snapshot }] of entries) {
    clearTimeout(timer)
    write(key, snapshot)
  }
}

if (typeof window !== 'undefined') {
  window.addEventListener('pagehide', flushDraftWrites)
}
