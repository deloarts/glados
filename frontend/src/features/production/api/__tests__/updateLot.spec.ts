import { describe, it, expect, vi, beforeEach } from 'vitest'

const patchMock = vi.fn<(url: string, payload?: unknown) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: { patch: (url: string, payload?: unknown) => patchMock(url, payload) },
}))

import { updateLot } from '../updateLot'
import type { LotUpdateRequest } from '../../types/productionLotsRequest'
import type { LotResponse } from '../../types/productionLotsResponse'

describe('updateLot', () => {
  beforeEach(() => {
    patchMock.mockReset()
  })

  it('PATCHes the payload to /production-lots/{id} and returns the updated lot', async () => {
    const payload: LotUpdateRequest = { note: 'Priority rework', quantity: 8, expected_edit_version: 1 }
    const updated = { id: 4, lot_number: 'LOT-4' } as unknown as LotResponse
    patchMock.mockResolvedValue({ data: updated })

    const result = await updateLot(4, payload)

    expect(patchMock).toHaveBeenCalledWith('/production-lots/4', payload)
    expect(result).toBe(updated)
  })

  it('propagates a failed request instead of swallowing it', async () => {
    const error = new Error('404 not found')
    patchMock.mockRejectedValue(error)

    await expect(updateLot(4, { expected_edit_version: 0 })).rejects.toBe(error)
  })
})
