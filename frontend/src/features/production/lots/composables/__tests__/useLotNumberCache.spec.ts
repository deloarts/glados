import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

const getLotsByIdsMock = vi.fn<(ids: number[]) => Promise<unknown>>()

vi.mock('../../api/getLotsByIds', () => ({ getLotsByIds: (ids: number[]) => getLotsByIdsMock(ids) }))

import { useLotNumberCache, __resetLotNumberCache } from '../useLotNumberCache'

describe('useLotNumberCache', () => {
  beforeEach(() => {
    getLotsByIdsMock.mockReset()
    __resetLotNumberCache()
  })

  it('batches N distinct ids requested in the same tick into one API call', async () => {
    getLotsByIdsMock.mockResolvedValue([
      { id: 1, lot_number: 'LOT-1' },
      { id: 2, lot_number: 'LOT-2' },
      { id: 3, lot_number: 'LOT-3' },
    ])

    const { ensureLoaded, lotNumber } = useLotNumberCache()

    // Simulate N rows of a table each calling ensureLoaded for their own
    // lot id within the same synchronous tick.
    ensureLoaded(1)
    ensureLoaded(2)
    ensureLoaded(3)

    expect(getLotsByIdsMock).not.toHaveBeenCalled()

    await flushPromises()

    expect(getLotsByIdsMock).toHaveBeenCalledTimes(1)
    expect(getLotsByIdsMock).toHaveBeenCalledWith([1, 2, 3])

    expect(lotNumber(1)).toBe('LOT-1')
    expect(lotNumber(2)).toBe('LOT-2')
    expect(lotNumber(3)).toBe('LOT-3')
  })

  it('serves a repeat id from the cache without refetching', async () => {
    getLotsByIdsMock.mockResolvedValue([{ id: 1, lot_number: 'LOT-1' }])

    const { ensureLoaded, lotNumber } = useLotNumberCache()

    ensureLoaded(1)
    await flushPromises()
    expect(getLotsByIdsMock).toHaveBeenCalledTimes(1)

    // Same id requested again later (e.g. a second row referencing the same
    // lot), already cached, so no second request.
    ensureLoaded(1)
    await flushPromises()

    expect(getLotsByIdsMock).toHaveBeenCalledTimes(1)
    expect(lotNumber(1)).toBe('LOT-1')
  })

  it('does not queue a second request for an id already in flight', async () => {
    let resolveFetch!: (value: unknown) => void
    getLotsByIdsMock.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve
      }),
    )

    const { ensureLoaded } = useLotNumberCache()

    ensureLoaded(5)
    await flushPromises()
    expect(getLotsByIdsMock).toHaveBeenCalledTimes(1)

    // Requested again while the first request is still pending: must not
    // start a second batch.
    ensureLoaded(5)
    await flushPromises()
    expect(getLotsByIdsMock).toHaveBeenCalledTimes(1)

    resolveFetch([{ id: 5, lot_number: 'LOT-5' }])
    await flushPromises()
  })
})
