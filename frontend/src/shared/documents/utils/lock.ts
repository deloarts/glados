import type { ControlledDocument } from '../types'

/** Who is editing the document right now, or null once nobody holds a lock that is still running. */
export function editingBy(
  document: Pick<ControlledDocument, 'locked_by_id' | 'locked_by_full_name' | 'lock_expires_at'>,
  now: number = Date.now(),
): string | null {
  if (document.locked_by_id == null) return null
  const expires = document.lock_expires_at ? Date.parse(document.lock_expires_at) : Number.NaN
  if (!Number.isNaN(expires) && expires <= now) return null
  return document.locked_by_full_name ?? ''
}
