import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useUsersStore } from '@/core/stores/usersStore'
import type { UserGroupResponse } from '../../types/userGroup'

const getUserGroupsMock = vi.fn<() => Promise<UserGroupResponse[]>>()
const deleteUserGroupMock = vi.fn<(id: number) => Promise<void>>()

vi.mock('../../api/userGroups', () => ({
  getUserGroups: () => getUserGroupsMock(),
  createUserGroup: () => Promise.reject(new Error('not used')),
  updateUserGroup: () => Promise.reject(new Error('not used')),
  deleteUserGroup: (id: number) => deleteUserGroupMock(id),
}))
vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: () => Promise.resolve({ items: [], total: 0, limit: 100, skip: 0 }),
}))

import { useUserGroupsStore } from '../userGroupsStore'
import { useUserManagementStore } from '../userManagementStore'

function group(id: number, name: string, description = ''): UserGroupResponse {
  return {
    id,
    public_id: `00000000-0000-0000-0000-00000000000${id}`,
    created: '2026-11-01T00:00:00Z',
    changed: null,
    name,
    description,
    permissions: [],
    member_ids: [],
    creator_id: 1,
    changed_by_id: null,
    changed_by: null,
  }
}

describe('userGroupsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getUserGroupsMock.mockReset()
    deleteUserGroupMock.mockReset()
  })

  it('searches the name and the description', async () => {
    getUserGroupsMock.mockResolvedValue([group(1, 'Purchasing'), group(2, 'QA', 'quality checks')])
    const store = useUserGroupsStore()
    await store.refresh()

    store.search = 'qual'
    expect(store.filteredItems.map((g) => g.id)).toEqual([2])
    expect(store.hasActiveFilters).toBe(true)

    store.clearAll()
    expect(store.filteredItems.map((g) => g.id)).toEqual([1, 2])
  })

  it('refreshes the users after a write, since their permissions changed', async () => {
    getUserGroupsMock.mockResolvedValue([])
    deleteUserGroupMock.mockResolvedValue()
    const store = useUserGroupsStore()
    const users = useUsersStore()
    const refreshUsers = vi.spyOn(users, 'refresh')
    const management = useUserManagementStore()

    await store.remove(1)

    expect(deleteUserGroupMock).toHaveBeenCalledWith(1)
    expect(refreshUsers).toHaveBeenCalled()
    expect(management.refreshTrigger).toBe(1)
  })
})
