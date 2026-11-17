import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { useUsersStore } from '@/core/stores/usersStore'
import { createUserGroup, deleteUserGroup, getUserGroups, updateUserGroup } from '../api/userGroups'
import { useUserManagementStore } from './userManagementStore'

import type { SaveUserGroupRequest, UserGroupResponse } from '../types/userGroup'

/**
 * The user groups, all of them: a tenant holds a handful, so the list is
 * fetched whole and searched in the browser. A write changes what the
 * members may do, so it also refreshes the users the other tabs and pickers
 * show.
 */
export const useUserGroupsStore = defineStore('userGroups', () => {
  const fetch = useSequencedFetch(getUserGroups)
  const loading = computed(() => fetch.loading.value)
  const error = computed(() => fetch.error.value)
  const items = ref<UserGroupResponse[]>([])
  const search = ref('')
  const showActions = ref(false)
  const refreshTrigger = ref(0)

  const hasActiveFilters = computed(() => search.value.trim() !== '')

  const filteredItems = computed<UserGroupResponse[]>(() => {
    const term = search.value.trim().toLowerCase()
    if (!term) return items.value
    return items.value.filter(
      (g) => g.name.toLowerCase().includes(term) || g.description.toLowerCase().includes(term),
    )
  })

  async function refresh(): Promise<void> {
    const response = await fetch.run()
    if (response) items.value = response
  }

  function ensureLoaded(): Promise<void> {
    return items.value.length > 0 ? Promise.resolve() : refresh()
  }

  function getById(groupId: number): UserGroupResponse | undefined {
    return items.value.find((g) => g.id === groupId)
  }

  function triggerRefresh(): void {
    refreshTrigger.value++
    void refresh()
  }

  function toggleShowActions(): void {
    showActions.value = !showActions.value
  }

  function clearAll(): void {
    search.value = ''
  }

  function afterWrite(): void {
    void refresh()
    void useUsersStore().refresh()
    useUserManagementStore().triggerRefresh()
  }

  async function create(payload: SaveUserGroupRequest): Promise<UserGroupResponse> {
    const created = await createUserGroup(payload)
    afterWrite()
    return created
  }

  async function update(groupId: number, payload: SaveUserGroupRequest): Promise<UserGroupResponse> {
    const updated = await updateUserGroup(groupId, payload)
    afterWrite()
    return updated
  }

  async function remove(groupId: number): Promise<void> {
    await deleteUserGroup(groupId)
    afterWrite()
  }

  return {
    loading,
    error,
    items,
    filteredItems,
    search,
    showActions,
    refreshTrigger,
    hasActiveFilters,
    refresh,
    ensureLoaded,
    getById,
    triggerRefresh,
    toggleShowActions,
    clearAll,
    create,
    update,
    remove,
  }
})
