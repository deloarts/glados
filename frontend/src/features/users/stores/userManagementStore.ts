import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { FilterMatchMode } from '@openvue/core/api'
import type { DataTableFilterMeta } from 'openvue/datatable'

import { getUsers } from '@/core/api/users/getUsers'
import { updateUser } from '@/core/api/users/updateUser'
import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { useUserAvatarsStore } from '@/core/stores/userAvatarsStore'
import { useUsersStore } from '@/core/stores/usersStore'
import { filterMetaValue, hasActiveFilterMeta } from '@/core/utils/filterMeta'
import { createUser } from '../api/createUser'
import { deleteAllSessions } from '../api/deleteAllSessions'
import { deleteUserAvatar } from '../api/deleteUserAvatar'
import { deleteUserSession } from '../api/deleteUserSession'
import { deleteUserTimeTrackingCredentials } from '../api/deleteUserTimeTrackingCredentials'
import { resetUserTotp as resetUserTotpApi } from '../api/resetUserTotp'
import { fetchUserPasskeys, resetUserPasskeys } from '../api/userPasskeys'
import { uploadUserAvatar } from '../api/uploadUserAvatar'

import type {
  UserCreateRequest,
  UserFilterDto,
  UserSortBy,
  UserSortDir,
  UserUpdateRequest,
} from '@/core/types/userRequest'
import type { UserResponse } from '@/core/types/userResponse'

function createEmptyFilters(): DataTableFilterMeta {
  return {
    username: { value: null, matchMode: FilterMatchMode.CONTAINS },
    full_name: { value: null, matchMode: FilterMatchMode.CONTAINS },
    email: { value: null, matchMode: FilterMatchMode.CONTAINS },
    is_active: { value: null, matchMode: FilterMatchMode.EQUALS },
  }
}

/**
 * State and actions of the user administration table and form. Every write
 * also updates the lookup cache in core's usersStore, so the user pickers in
 * other features see the change without a refetch.
 */
export const useUserManagementStore = defineStore('userManagement', () => {
  const lookup = useUsersStore()
  // A tracker of its own, so a table page fetch never discards an in-flight
  // picker fetch as superseded, or the other way round.
  const tableFetch = useSequencedFetch(getUsers)
  const loading = computed(() => lookup.loading || tableFetch.loading.value)
  const error = computed(() => lookup.error ?? tableFetch.error.value)
  // The management table's current page.
  const tableItems = ref<UserResponse[]>([])
  const total = ref(0)
  const filters = ref<DataTableFilterMeta>(createEmptyFilters())
  const clearTrigger = ref(0)
  const refreshTrigger = ref(0)
  const showActions = ref(false)
  const sortBy = ref<UserSortBy | null>(null)
  const sortDir = ref<UserSortDir>('asc')

  const hasActiveFilters = computed<boolean>(() => hasActiveFilterMeta(filters.value))

  function buildParams(page?: { skip: number; limit: number }): UserFilterDto {
    const getValue = (field: string): unknown => filterMetaValue(filters.value, field)

    const params: UserFilterDto = {}

    const username = getValue('username')
    if (username) params.username = username as string

    const full_name = getValue('full_name')
    if (full_name) params.full_name = full_name as string

    const email = getValue('email')
    if (email) params.email = email as string

    const is_active = getValue('is_active')
    if (is_active !== null && is_active !== undefined) params.is_active = is_active as boolean

    if (sortBy.value) {
      params.order_by = sortBy.value
      params.order_dir = sortDir.value
    }

    if (page) {
      params.skip = page.skip
      params.limit = page.limit
    }

    return params
  }

  // The management table's fetch: paginated, feeds `tableItems`/`total`.
  async function refreshTable(page?: { skip: number; limit: number }): Promise<void> {
    const response = await tableFetch.run(buildParams(page))
    if (!response) return

    tableItems.value = response.items
    total.value = response.total
  }

  function triggerRefresh(): void {
    refreshTrigger.value++
  }

  function clearAll(): void {
    filters.value = createEmptyFilters()
    clearTrigger.value++
  }

  function toggleShowActions(): void {
    showActions.value = !showActions.value
  }

  function setSort(field: UserSortBy, dir: UserSortDir): void {
    sortBy.value = field
    sortDir.value = dir
  }

  function clearSort(): void {
    sortBy.value = null
    sortDir.value = 'asc'
  }

  async function create(payload: UserCreateRequest): Promise<UserResponse> {
    const created = await createUser(payload)

    lookup.add(created)
    triggerRefresh()

    return created
  }

  async function update(userId: number, payload: UserUpdateRequest): Promise<UserResponse> {
    const updated = await updateUser(userId, payload)

    lookup.replace(updated)
    triggerRefresh()

    return updated
  }

  async function uploadAvatar(userId: number, file: File): Promise<UserResponse> {
    const updated = await uploadUserAvatar(userId, file)
    lookup.replace(updated)
    useUserAvatarsStore().invalidate(userId)
    triggerRefresh()
    return updated
  }

  async function deleteAvatar(userId: number): Promise<UserResponse> {
    const updated = await deleteUserAvatar(userId)
    lookup.replace(updated)
    useUserAvatarsStore().invalidate(userId)
    triggerRefresh()
    return updated
  }

  async function resetTotp(userId: number): Promise<void> {
    await resetUserTotpApi(userId)

    triggerRefresh()
  }

  /** Passkeys are not part of the user row, so the list needs no refresh. */
  async function countPasskeys(userId: number): Promise<number> {
    return (await fetchUserPasskeys(userId)).length
  }

  async function resetPasskeys(userId: number): Promise<number> {
    return resetUserPasskeys(userId)
  }

  /**
   * The stored credentials are not part of the user row, so nothing in
   * the list changes.
   */
  async function removeTimeTrackingCredentials(userId: number): Promise<void> {
    await deleteUserTimeTrackingCredentials(userId)
  }

  async function terminateSession(userId: number): Promise<void> {
    await deleteUserSession(userId)

    triggerRefresh()
  }

  async function terminateAllSessions(): Promise<void> {
    await deleteAllSessions()

    triggerRefresh()
  }

  return {
    loading,
    error,
    tableItems,
    total,
    filters,
    clearTrigger,
    refreshTrigger,
    showActions,
    sortBy,
    sortDir,

    hasActiveFilters,

    refreshTable,
    triggerRefresh,
    clearAll,
    toggleShowActions,
    setSort,
    clearSort,
    create,
    update,
    uploadAvatar,
    deleteAvatar,
    resetTotp,
    countPasskeys,
    resetPasskeys,
    removeTimeTrackingCredentials,
    terminateSession,
    terminateAllSessions,
  }
})
