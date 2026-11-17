import { describe, it, expect, vi, beforeEach } from 'vitest'

const postMock = vi.fn<(url: string, payload?: unknown) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: { post: (url: string, payload?: unknown) => postMock(url, payload) },
}))

import { createLot } from '../createLot'
import type { LotCreateRequest } from '../../types/productionLotsRequest'
import type { LotResponse } from '../../types/productionLotsResponse'

describe('createLot', () => {
  beforeEach(() => {
    postMock.mockReset()
  })

  it('POSTs the payload to /production-lots and returns the created lot', async () => {
    const payload: LotCreateRequest = { made_item_id: 1, project_id: 2, quantity: 10 }
    const created = { id: 3, lot_number: 'LOT-3' } as unknown as LotResponse
    postMock.mockResolvedValue({ data: created })

    const result = await createLot(payload)

    expect(postMock).toHaveBeenCalledWith('/production-lots/', payload)
    expect(result).toBe(created)
  })

  it('propagates a failed request instead of swallowing it', async () => {
    const error = new Error('422 validation')
    postMock.mockRejectedValue(error)

    await expect(createLot({ made_item_id: 1, project_id: 2, quantity: 1 })).rejects.toBe(error)
  })
})
