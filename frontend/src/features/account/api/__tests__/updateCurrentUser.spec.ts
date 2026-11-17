import { describe, it, expect, vi, beforeEach } from 'vitest'

const putMock = vi.fn<(url: string, payload?: unknown) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: { put: (url: string, payload?: unknown) => putMock(url, payload) },
}))

import { updateCurrentUser } from '../updateCurrentUser'
import type { UserUpdateRequest } from '@/core/types/userRequest'
import type { UserResponse } from '@/core/types/userResponse'

describe('updateCurrentUser', () => {
  beforeEach(() => {
    putMock.mockReset()
  })

  it('PUTs the payload to /users/me and returns the updated user', async () => {
    const payload: UserUpdateRequest = { full_name: 'Ada Lovelace' }
    const updated = { id: 1, full_name: 'Ada Lovelace' } as unknown as UserResponse
    putMock.mockResolvedValue({ data: updated })

    const result = await updateCurrentUser(payload)

    expect(putMock).toHaveBeenCalledWith('/users/me', payload)
    expect(result).toBe(updated)
  })

  it('propagates a failed request instead of swallowing it', async () => {
    const error = new Error('422 validation')
    putMock.mockRejectedValue(error)

    await expect(updateCurrentUser({ full_name: 'Ada Lovelace' })).rejects.toBe(error)
  })
})
