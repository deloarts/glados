import { describe, it, expect, vi } from 'vitest'

import { refreshOnConflict } from '../refreshOnConflict'

function apiError(status: number) {
  return { isAxiosError: true, response: { status, data: { detail: 'refused' } } }
}

describe('refreshOnConflict', () => {
  it('returns the result and leaves the view alone when the action succeeds', async () => {
    const refresh = vi.fn<() => void>()

    await expect(refreshOnConflict(() => Promise.resolve(7), refresh)).resolves.toBe(7)
    expect(refresh).not.toHaveBeenCalled()
  })

  it('refreshes after a 409 and passes the error on', async () => {
    const refresh = vi.fn<() => Promise<void>>().mockResolvedValue()
    const error = apiError(409)

    await expect(refreshOnConflict(() => Promise.reject(error), refresh)).rejects.toBe(error)
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('keeps the 409 as the error when the refresh fails too', async () => {
    const error = apiError(409)
    const refresh = vi.fn<() => Promise<void>>().mockRejectedValue(new Error('offline'))

    await expect(refreshOnConflict(() => Promise.reject(error), refresh)).rejects.toBe(error)
  })

  it('does not refresh after any other error', async () => {
    const refresh = vi.fn<() => void>()

    await expect(
      refreshOnConflict(() => Promise.reject(apiError(422)), refresh),
    ).rejects.toMatchObject({ response: { status: 422 } })
    expect(refresh).not.toHaveBeenCalled()
  })
})
