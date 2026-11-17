/**
 * The accounts that signed in on this device, so the login page can offer
 * them again with name and avatar instead of an empty form. Kept in this
 * browser's localStorage only and never sent anywhere. Nothing secret is
 * stored: the passkey's credential ID only tells the browser which of its
 * passkeys to offer, the private key stays in the authenticator.
 *
 * Every access is wrapped, because storage can be unavailable (private
 * windows, blocked site data), and the login page must work without it.
 */

const STORAGE_KEY = 'glados.rememberedUsers'
const MAX_REMEMBERED = 5

export interface RememberedUser {
  username: string
  fullName: string
  /** A small data URL, so the avatar shows before anyone is signed in. */
  avatar: string | null
  /** base64url credential ID of the passkey this device registered, if any. */
  credentialId: string | null
  /** public_id of that passkey, to forget the ID when the passkey is removed. */
  passkeyPublicId: string | null
  /** The user said "Not Now" to setting up a passkey on this device. */
  passkeyDeclined: boolean
  lastSignedInAt: string
}

function isRememberedUser(value: unknown): value is RememberedUser {
  const entry = value as Partial<RememberedUser> | null
  return (
    typeof entry?.username === 'string' &&
    entry.username !== '' &&
    typeof entry.fullName === 'string' &&
    typeof entry.lastSignedInAt === 'string'
  )
}

function read(): RememberedUser[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    // Hand-edited or outdated entries are dropped rather than trusted.
    return Array.isArray(parsed) ? parsed.filter(isRememberedUser) : []
  } catch {
    return []
  }
}

function write(users: RememberedUser[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(users.slice(0, MAX_REMEMBERED)))
  } catch {
    // Storage full or blocked: the login page simply shows the plain form.
  }
}

/** Most recent sign-in first. */
export function listRememberedUsers(): RememberedUser[] {
  return read().sort((a, b) => b.lastSignedInAt.localeCompare(a.lastSignedInAt))
}

export function findRememberedUser(username: string): RememberedUser | null {
  return read().find((u) => u.username === username) ?? null
}

/** Records a sign-in, keeping what this device already knew about the user. */
export function rememberUser(
  update: Pick<RememberedUser, 'username' | 'fullName'> & Partial<RememberedUser>,
): RememberedUser {
  const users = read()
  const existing = users.find((u) => u.username === update.username)
  const merged: RememberedUser = {
    avatar: null,
    credentialId: null,
    passkeyPublicId: null,
    passkeyDeclined: false,
    ...existing,
    ...update,
    lastSignedInAt: new Date().toISOString(),
  }
  write([merged, ...users.filter((u) => u.username !== update.username)])
  return merged
}

export function updateRememberedUser(username: string, patch: Partial<RememberedUser>): void {
  write(read().map((u) => (u.username === username ? { ...u, ...patch } : u)))
}

export function forgetRememberedUser(username: string): void {
  write(read().filter((u) => u.username !== username))
}

/** Drops the stored credential ID wherever it belongs to a passkey that no longer exists. */
export function forgetPasskey(passkeyPublicId: string): void {
  write(
    read().map((u) =>
      u.passkeyPublicId === passkeyPublicId ? { ...u, credentialId: null, passkeyPublicId: null } : u,
    ),
  )
}

/** Drops the stored credential ID of a user whose passkeys were all removed. */
export function forgetPasskeysOf(username: string): void {
  updateRememberedUser(username, { credentialId: null, passkeyPublicId: null })
}

/** Up to two initials for an account without an avatar. */
export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}

/** Shrinks an avatar to a small JPEG data URL, so it fits comfortably in localStorage. */
export async function avatarToDataUrl(blob: Blob, size = 96): Promise<string | null> {
  try {
    const bitmap = await createImageBitmap(blob)
    const canvas = document.createElement('canvas')
    canvas.width = size
    canvas.height = size
    const context = canvas.getContext('2d')
    if (!context) return null
    const side = Math.min(bitmap.width, bitmap.height)
    context.drawImage(
      bitmap,
      (bitmap.width - side) / 2,
      (bitmap.height - side) / 2,
      side,
      side,
      0,
      0,
      size,
      size,
    )
    return canvas.toDataURL('image/jpeg', 0.85)
  } catch {
    return null
  }
}
