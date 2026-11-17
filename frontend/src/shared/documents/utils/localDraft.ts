/**
 * Unsaved changes of a document, kept in this browser so they survive a
 * reload, a closed tab, a crash or an expired session. Each copy belongs to
 * one user and one document, and remembers when the document was last saved
 * on the server, so a copy is never taken for newer than a later save.
 *
 * A copy goes when its changes are saved, thrown away on purpose or its
 * document is deleted, and on its own once it is older than MAX_AGE_DAYS;
 * signing out or a session running out keeps it, and the app offers it
 * only to the user who wrote it. Storage that is full, blocked or missing is
 * treated as empty.
 */

import { safeStorage } from '@/core/utils/safeStorage'

const PREFIX = 'glados.documentDraft.'
/** Ten weeks, long enough for a holiday, short enough not to pile up. */
export const MAX_AGE_DAYS = 70

export interface LocalDraft<V> {
  /** When the copy was written, ISO 8601. */
  savedAt: string
  /** The document's last save on the server when the copy was written, null for a document never saved. */
  base: string | null
  value: V
}

function storageKey(userId: number, key: string): string {
  return `${PREFIX}${userId}.${key}`
}

function isDraft(value: unknown): value is LocalDraft<unknown> {
  if (typeof value !== 'object' || value === null) return false
  const draft = value as Record<string, unknown>
  return typeof draft.savedAt === 'string' && (draft.base === null || typeof draft.base === 'string') && 'value' in draft
}

function expired(draft: LocalDraft<unknown>, now: number): boolean {
  const savedAt = Date.parse(draft.savedAt)
  return Number.isNaN(savedAt) || now - savedAt > MAX_AGE_DAYS * 24 * 60 * 60 * 1000
}

/** The copy of `key` for the user, or null when there is none or it is unreadable or too old. */
export function readLocalDraft<V>(userId: number, key: string): LocalDraft<V> | null {
  const raw = safeStorage.get(storageKey(userId, key))
  if (raw === null) return null
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return null
  }
  if (!isDraft(parsed) || expired(parsed, Date.now())) {
    safeStorage.remove(storageKey(userId, key))
    return null
  }
  return parsed as LocalDraft<V>
}

export function writeLocalDraft<V>(userId: number, key: string, value: V, base: string | null): void {
  const draft: LocalDraft<V> = { savedAt: new Date().toISOString(), base, value }
  // A full or blocked storage keeps nothing; the page still works.
  safeStorage.set(storageKey(userId, key), JSON.stringify(draft))
}

export function removeLocalDraft(userId: number, key: string): void {
  safeStorage.remove(storageKey(userId, key))
}

/** Drops every copy, of any user, that is older than MAX_AGE_DAYS or unreadable. */
export function pruneLocalDrafts(): void {
  const now = Date.now()
  for (const key of safeStorage.keys().filter((k) => k.startsWith(PREFIX))) {
    let parsed: unknown = null
    try {
      parsed = JSON.parse(safeStorage.get(key) ?? 'null')
    } catch {
      parsed = null
    }
    if (!isDraft(parsed) || expired(parsed, now)) safeStorage.remove(key)
  }
}
