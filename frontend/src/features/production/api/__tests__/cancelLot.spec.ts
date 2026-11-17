import { describe, it, expect, vi, beforeEach } from 'vitest'

const postMock = vi.fn<(url: string, payload?: unknown) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: { post: (url: string, payload?: unknown) => postMock(url, payload) },
}))

import { cancelLot } from '../cancelLot'
import type { LotResponse } from '../../types/productionLotsResponse'

describe('cancelLot', () => {
  beforeEach(() => {
    postMock.mockReset()
  })

  it('POSTs only the edit version to /production-lots/{id}/cancel when no reason is given', async () => {
    const cancelled = { id: 6, status: 'canceled' } as unknown as LotResponse
    postMock.mockResolvedValue({ data: cancelled })

    const result = await cancelLot(6, { expected_edit_version: 2 })

    expect(postMock).toHaveBeenCalledWith('/production-lots/6/cancel', { expected_edit_version: 2 })
    expect(result).toBe(cancelled)
  })

  it('POSTs the given reason when provided', async () => {
    postMock.mockResolvedValue({ data: {} as LotResponse })

    await cancelLot(6, { reason: 'Wrong material', expected_edit_version: 2 })

    expect(postMock).toHaveBeenCalledWith('/production-lots/6/cancel', {
      reason: 'Wrong material',
      expected_edit_version: 2,
    })
  })
})
