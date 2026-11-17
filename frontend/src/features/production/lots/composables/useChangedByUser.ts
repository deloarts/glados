import { useUsersStore } from '@/core/stores/usersStore'

import type { PublicUser } from '@/core/types/userResponse'

export interface ChangelogEntryLike {
  username: string
}

export interface ChangedBy {
  // Null when nothing changed yet or the changelog name matches no user.
  user: PublicUser | null
  // The raw changelog name, for a plain-text fallback.
  name: string | null
}

/**
 * Resolves who last changed a record by matching the changelog's actor name
 * against the loaded users, since the changelog stores only a name.
 */
export function useChangedByUser() {
  const usersStore = useUsersStore()

  function resolve(entries: ChangelogEntryLike[]): ChangedBy {
    const name = entries[entries.length - 1]?.username ?? null
    if (!name) return { user: null, name: null }
    return { user: usersStore.users.find((u) => u.full_name === name) ?? null, name }
  }

  return { resolve }
}
