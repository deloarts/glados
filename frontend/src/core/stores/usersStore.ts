import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getUserDirectory } from '@/core/api/users/getUserDirectory'
import { useSequencedFetch } from '@/core/composables/useSequencedFetch'

import type { UserSummary } from '@/core/types/userResponse'

export interface UserOption {
  text: string
  value: number
}

/**
 * The user lookup cache other features read to name and pick users. It holds
 * the reduced directory view every signed-in user may read, never e-mail or
 * permissions. User administration keeps its table state and write actions
 * in the users feature's own store, which writes changed users back here so
 * the pickers stay current without a refetch.
 */
export const useUsersStore = defineStore('users', () => {
  const pickerFetch = useSequencedFetch(getUserDirectory)
  const loading = computed(() => pickerFetch.loading.value)
  const error = computed(() => pickerFetch.error.value)
  // The picker-facing, unpaginated list: ProjectFormDialog, OrdersTable,
  // LotsTable, ... read this as the *complete* user list (see getById/
  // getNameById/userOptions below). Paging the management table must not
  // shrink what those pickers see, so the table keeps its page in its own
  // store.
  const users = ref<UserSummary[]>([])

  const userOptions = computed<UserOption[]>(() => {
    return users.value.map((user) => ({
      text: user.full_name,
      value: user.id,
    }))
  })

  const userOptionsWithAll = computed<UserOption[]>(() => {
    return [
      {
        text: 'All',
        value: 0,
      },
      ...userOptions.value,
    ]
  })

  // The picker-facing fetch: feeds `users`, the complete (unpaginated,
  // aside from the backend's own default page size) list other features read.
  // It sends no params, so the management table's filters and sort never
  // narrow the pickers. Without an is_active filter the backend returns
  // inactive users too, so pickers can still name an inactive creator.
  async function refresh(): Promise<void> {
    const response = await pickerFetch.run({})
    if (!response) return

    users.value = response.items
  }

  // The picker fetch shared by every ensureLoaded() caller while it runs.
  let ensureInFlight: Promise<void> | null = null

  // Loads the picker list once, for the components that only need it to be
  // there: a no-op when it is already filled, and callers that arrive while
  // that first load runs share its request instead of starting their own.
  function ensureLoaded(): Promise<void> {
    if (users.value.length > 0) return Promise.resolve()
    if (!ensureInFlight) {
      ensureInFlight = refresh().finally(() => {
        ensureInFlight = null
      })
    }
    return ensureInFlight
  }

  function clear(): void {
    users.value = []
  }

  function getById(userId: number): UserSummary | undefined {
    return users.value.find((user) => user.id === userId)
  }

  function getNameById(userId: number | null): string {
    if (userId == null) {
      return ''
    }

    return getById(userId)?.full_name ?? 'Unknown User'
  }

  function add(user: UserSummary): void {
    users.value.push(user)
  }

  /** Replaces the cached copy of a user, if the cache holds one. */
  function replace(user: UserSummary): void {
    const index = users.value.findIndex((u) => u.id === user.id)
    if (index !== -1) users.value[index] = user
  }

  return {
    loading,
    error,
    users,

    userOptions,
    userOptionsWithAll,

    refresh,
    ensureLoaded,
    clear,
    getById,
    getNameById,
    add,
    replace,
  }
})
