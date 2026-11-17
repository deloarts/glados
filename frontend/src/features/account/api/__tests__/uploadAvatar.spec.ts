import { describe, it, expect, vi, beforeEach } from 'vitest'

const postMock =
  vi.fn<(url: string, payload?: unknown, config?: unknown) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: { post: (url: string, payload?: unknown, config?: unknown) => postMock(url, payload, config) },
}))

import { uploadAvatar } from '../uploadAvatar'
import type { UserResponse } from '@/core/types/userResponse'

describe('uploadAvatar', () => {
  beforeEach(() => {
    postMock.mockReset()
  })

  it('POSTs a multipart FormData body to /users/me/avatar and returns the updated user', async () => {
    const updated = { id: 1, avatar_url: '/avatars/1.png' } as unknown as UserResponse
    postMock.mockResolvedValue({ data: updated })
    const file = new File(['binary'], 'avatar.png', { type: 'image/png' })

    const result = await uploadAvatar(file)

    expect(postMock).toHaveBeenCalledTimes(1)
    const [url, formData, config] = postMock.mock.calls[0] as [string, FormData, { headers: Record<string, string> }]
    expect(url).toBe('/users/me/avatar')
    expect(formData).toBeInstanceOf(FormData)
    expect(formData.get('file')).toBe(file)
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
    expect(result).toBe(updated)
  })

  it('propagates a failed request instead of swallowing it', async () => {
    const error = new Error('413 too large')
    postMock.mockRejectedValue(error)

    await expect(uploadAvatar(new File(['x'], 'a.png'))).rejects.toBe(error)
  })
})
