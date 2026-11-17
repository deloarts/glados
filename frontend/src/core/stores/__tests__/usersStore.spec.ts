import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type { UserDirectoryFilterDto } from '@/core/types/userRequest'
import type { UserSummary } from '@/core/types/userResponse'

const getUserDirectoryMock =
  vi.fn<(params?: UserDirectoryFilterDto) => Promise<PageResponse<UserSummary>>>()

vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: (params?: UserDirectoryFilterDto) => getUserDirectoryMock(params),
}))

import { useUsersStore } from '../usersStore'
import { makeUserResponse } from '@/test-utils/factories'

function page(items: UserSummary[], total = items.length): PageResponse<UserSummary> {
  return { items, total, limit: 25, skip: 0 }
}

describe('usersStore ensureLoaded', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getUserDirectoryMock.mockReset()
  })

  it('loads the picker list once and shares the request with callers that arrive meanwhile', async () => {
    getUserDirectoryMock.mockResolvedValue(page([makeUserResponse()]))
    const store = useUsersStore()

    await Promise.all([store.ensureLoaded(), store.ensureLoaded()])

    expect(getUserDirectoryMock).toHaveBeenCalledTimes(1)
    expect(store.users).toHaveLength(1)
  })

  it('does not fetch when the picker list is already filled', async () => {
    const store = useUsersStore()
    store.users = [makeUserResponse()]

    await store.ensureLoaded()

    expect(getUserDirectoryMock).not.toHaveBeenCalled()
  })

  it('fetches again after an empty answer', async () => {
    getUserDirectoryMock.mockResolvedValue(page([]))
    const store = useUsersStore()

    await store.ensureLoaded()
    await store.ensureLoaded()

    expect(getUserDirectoryMock).toHaveBeenCalledTimes(2)
  })
})
