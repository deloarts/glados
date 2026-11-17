import { describe, it, expect, vi, beforeEach } from 'vitest'

const deleteMock = vi.fn<(url: string) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: { delete: (url: string) => deleteMock(url) },
}))

import { deleteAvatar } from '../deleteAvatar'
import type { UserResponse } from '@/core/types/userResponse'

describe('deleteAvatar', () => {
  beforeEach(() => {
    deleteMock.mockReset()
  })

  it('DELETEs /users/me/avatar and returns the updated user', async () => {
    const updated = { id: 1, avatar_url: null } as unknown as UserResponse
    deleteMock.mockResolvedValue({ data: updated })

    const result = await deleteAvatar()

    expect(deleteMock).toHaveBeenCalledWith('/users/me/avatar')
    expect(result).toBe(updated)
  })

  it('propagates a failed request instead of swallowing it', async () => {
    const error = new Error('network down')
    deleteMock.mockRejectedValue(error)

    await expect(deleteAvatar()).rejects.toBe(error)
  })
})
