import { describe, it, expect, vi, beforeEach } from 'vitest'

const putMock = vi.fn<(url: string, payload?: unknown) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: { put: (url: string, payload?: unknown) => putMock(url, payload) },
}))

import { reassignProductionOrderMachine } from '../reassignProductionOrderMachine'
import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'

describe('reassignProductionOrderMachine', () => {
  beforeEach(() => {
    putMock.mockReset()
    putMock.mockResolvedValue({ data: {} as ProductionOrderResponse })
  })

  it('PUTs a machine_id-only payload to /production-orders/{id}/machine', async () => {
    await reassignProductionOrderMachine(1, { machine_id: 9 })

    expect(putMock).toHaveBeenCalledWith('/production-orders/1/machine', { machine_id: 9 })
  })

  it('PUTs a machine_pool_id-only payload, never mixing it with machine_id', async () => {
    await reassignProductionOrderMachine(1, { machine_pool_id: 3 })

    const [, payload] = putMock.mock.calls[0]!
    expect(payload).toEqual({ machine_pool_id: 3 })
    expect(payload).not.toHaveProperty('machine_id')
  })

  it('allows clearing a direct machine assignment with machine_id: null', async () => {
    await reassignProductionOrderMachine(1, { machine_id: null })

    expect(putMock).toHaveBeenCalledWith('/production-orders/1/machine', { machine_id: null })
  })

  it('returns the response data', async () => {
    const updated = { id: 1, machine_id: 9 } as unknown as ProductionOrderResponse
    putMock.mockResolvedValue({ data: updated })

    const result = await reassignProductionOrderMachine(1, { machine_id: 9 })

    expect(result).toBe(updated)
  })
})
