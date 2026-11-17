import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { AxiosError, AxiosHeaders } from 'axios'

import type { PageResponse } from '@/core/api/types'
import type { UserCreateRequest, UserFilterDto, UserUpdateRequest } from '@/core/types/userRequest'
import type { UserResponse } from '@/core/types/userResponse'

const getUsersMock = vi.fn<(params?: UserFilterDto) => Promise<PageResponse<UserResponse>>>()
const createUserMock = vi.fn<(payload: UserCreateRequest) => Promise<UserResponse>>()
const updateUserMock = vi.fn<(id: number, payload: UserUpdateRequest) => Promise<UserResponse>>()

vi.mock('@/core/api/users/getUsers', () => ({
  getUsers: (params?: UserFilterDto) => getUsersMock(params),
}))
// The user pickers read the directory, user administration the full list.
vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: (params?: UserFilterDto) => getUsersMock(params),
}))
vi.mock('../../api/createUser', () => ({
  createUser: (payload: UserCreateRequest) => createUserMock(payload),
}))
vi.mock('@/core/api/users/updateUser', () => ({
  updateUser: (id: number, payload: UserUpdateRequest) => updateUserMock(id, payload),
}))
vi.mock('../../api/deleteAllSessions', () => ({ deleteAllSessions: vi.fn<() => void>() }))
vi.mock('../../api/deleteUserAvatar', () => ({ deleteUserAvatar: vi.fn<() => void>() }))
vi.mock('../../api/deleteUserSession', () => ({ deleteUserSession: vi.fn<() => void>() }))
vi.mock('../../api/resetUserTotp', () => ({ resetUserTotp: vi.fn<() => void>() }))
vi.mock('../../api/uploadUserAvatar', () => ({ uploadUserAvatar: vi.fn<() => void>() }))

import { useUsersStore } from '@/core/stores/usersStore'
import { useUserManagementStore } from '../userManagementStore'
import { makeUserResponse } from '@/test-utils/factories'

function page(items: UserResponse[], total = items.length): PageResponse<UserResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('userManagementStore pagination', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getUsersMock.mockReset()
    createUserMock.mockReset()
    updateUserMock.mockReset()
  })

  it('refreshTable sends skip/limit and populates tableItems/total from the envelope', async () => {
    getUsersMock.mockResolvedValue(page([makeUserResponse()], 42))
    const store = useUserManagementStore()

    await store.refreshTable({ skip: 25, limit: 25 })

    expect(getUsersMock).toHaveBeenCalledWith(expect.objectContaining({ skip: 25, limit: 25 }))
    expect(store.tableItems).toHaveLength(1)
    expect(store.total).toBe(42)
  })

  it('ignores a slower, older table response that resolves after a newer one', async () => {
    let resolveSlow: (value: PageResponse<UserResponse>) => void = () => {}
    getUsersMock
      .mockReturnValueOnce(new Promise((resolve) => (resolveSlow = resolve)))
      .mockResolvedValueOnce(page([makeUserResponse({ id: 2 })], 1))
    const store = useUserManagementStore()

    const slow = store.refreshTable({ skip: 0, limit: 25 })
    await store.refreshTable({ skip: 25, limit: 25 })
    resolveSlow(page([makeUserResponse({ id: 1 })], 99))
    await slow

    expect(store.tableItems.map((u) => u.id)).toEqual([2])
    expect(store.total).toBe(1)
  })

  it('records a failed table fetch in error instead of throwing', async () => {
    const config = { headers: new AxiosHeaders() }
    getUsersMock.mockRejectedValueOnce(
      new AxiosError('Request failed', '500', config, undefined, {
        data: { detail: 'boom' },
        status: 500,
        statusText: 'Internal Server Error',
        headers: {},
        config,
      }),
    )
    const store = useUserManagementStore()

    await expect(store.refreshTable({ skip: 0, limit: 25 })).resolves.toBeUndefined()

    expect(store.error).toBe('boom')
    expect(store.loading).toBe(false)
  })

  it('threads the row filters into refreshTable alongside skip/limit', async () => {
    getUsersMock.mockResolvedValue(page([]))
    const store = useUserManagementStore()
    store.filters.username = { value: 'jdoe', matchMode: 'contains' }

    await store.refreshTable({ skip: 0, limit: 25 })

    expect(getUsersMock).toHaveBeenCalledWith(
      expect.objectContaining({ username: 'jdoe', skip: 0, limit: 25 }),
    )
  })

  it('threads order_by/order_dir into refreshTable once setSort is called, and clearSort drops them', async () => {
    getUsersMock.mockResolvedValue(page([]))
    const store = useUserManagementStore()

    store.setSort('username', 'desc')
    await store.refreshTable({ skip: 0, limit: 25 })
    expect(getUsersMock).toHaveBeenCalledWith(
      expect.objectContaining({ order_by: 'username', order_dir: 'desc' }),
    )

    getUsersMock.mockClear()
    store.clearSort()
    await store.refreshTable({ skip: 0, limit: 25 })
    expect(getUsersMock).toHaveBeenCalledWith(
      expect.not.objectContaining({ order_by: expect.anything() }),
    )
  })

  it('keeps the picker-facing refresh() unpaginated and separate from tableItems', async () => {
    getUsersMock.mockResolvedValue(page([makeUserResponse({ id: 9 })], 1))
    const store = useUserManagementStore()
    const lookup = useUsersStore()

    await lookup.refresh()

    expect(getUsersMock).toHaveBeenCalledWith(
      expect.not.objectContaining({ skip: expect.anything() }),
    )
    expect(lookup.users).toHaveLength(1)
    expect(store.tableItems).toHaveLength(0)
  })

  it('keeps the table filters and sort out of the picker-facing refresh()', async () => {
    getUsersMock.mockResolvedValue(
      page([makeUserResponse({ id: 9 }), makeUserResponse({ id: 10 })], 2),
    )
    const store = useUserManagementStore()
    store.filters.username = { value: 'jdoe', matchMode: 'contains' }
    store.filters.is_active = { value: false, matchMode: 'equals' }
    store.setSort('username', 'desc')
    const lookup = useUsersStore()

    await lookup.refresh()

    expect(getUsersMock).toHaveBeenCalledTimes(1)
    expect(getUsersMock).toHaveBeenCalledWith({})
    expect(lookup.users).toHaveLength(2)
  })

  it('bumps refreshTrigger independently so the table can react to it', () => {
    const store = useUserManagementStore()
    expect(store.refreshTrigger).toBe(0)
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
  })

  it('bumps refreshTrigger after create() so the management table refetches its page', async () => {
    const created = makeUserResponse({ id: 2, username: 'newbie' })
    createUserMock.mockResolvedValue(created)
    const store = useUserManagementStore()

    await store.create({
      username: 'newbie',
      full_name: 'New Bie',
      email: 'newbie@example.com',
      password: 'secret',
      is_active: true,
      is_shared_account: false,
      auth_provider: 'local',
      member_ids: [],
      group_ids: [],
      permissions: [],
    })

    expect(useUsersStore().users).toContainEqual(created)
    expect(store.refreshTrigger).toBe(1)
  })

  it('bumps refreshTrigger after update() so the management table refetches its page', async () => {
    const existing = makeUserResponse({ id: 3 })
    getUsersMock.mockResolvedValue(page([existing]))
    const store = useUserManagementStore()
    const lookup = useUsersStore()
    await lookup.refresh()

    const updated = { ...existing, full_name: 'Renamed' }
    updateUserMock.mockResolvedValue(updated)

    await store.update(3, { full_name: 'Renamed' })

    expect(lookup.users.find((u) => u.id === 3)?.full_name).toBe('Renamed')
    expect(store.refreshTrigger).toBe(1)
  })
})
