import { describe, it, expect, vi } from 'vitest'

import { API_MAX_PAGE_SIZE } from '@/core/constants/table'

import { fetchAllPages } from '../fetchAllPages'
import type { PageWindow } from '../fetchAllPages'
import type { PageResponse } from '../types'

function serve(all: number[]) {
  return vi.fn<(window: PageWindow) => Promise<PageResponse<number>>>(({ skip, limit }) =>
    Promise.resolve({ items: all.slice(skip, skip + limit), total: all.length, limit, skip }),
  )
}

describe('fetchAllPages', () => {
  it('requests consecutive windows until it holds the total', async () => {
    const all = Array.from({ length: 7 }, (_, i) => i)
    const fetchPage = serve(all)

    const result = await fetchAllPages(fetchPage, 3)

    expect(result).toEqual(all)
    expect(fetchPage.mock.calls.map(([window]) => window)).toEqual([
      { skip: 0, limit: 3 },
      { skip: 3, limit: 3 },
      { skip: 6, limit: 3 },
    ])
  })

  it('makes one request when the first page holds everything', async () => {
    const fetchPage = serve([1, 2])

    const result = await fetchAllPages(fetchPage)

    expect(result).toEqual([1, 2])
    expect(fetchPage).toHaveBeenCalledTimes(1)
    expect(fetchPage).toHaveBeenCalledWith({ skip: 0, limit: API_MAX_PAGE_SIZE })
  })

  it('never asks for more than the API maximum', async () => {
    const fetchPage = serve([])

    await fetchAllPages(fetchPage, API_MAX_PAGE_SIZE * 2)

    expect(fetchPage).toHaveBeenCalledWith({ skip: 0, limit: API_MAX_PAGE_SIZE })
  })

  it('stops on a short page even if the total claims more', async () => {
    const fetchPage = vi.fn<(window: PageWindow) => Promise<PageResponse<number>>>()
    fetchPage.mockResolvedValueOnce({ items: [1, 2], total: 5, limit: 2, skip: 0 })
    fetchPage.mockResolvedValueOnce({ items: [3], total: 5, limit: 2, skip: 2 })

    const result = await fetchAllPages(fetchPage, 2)

    expect(result).toEqual([1, 2, 3])
    expect(fetchPage).toHaveBeenCalledTimes(2)
  })

  it('stops on an empty page', async () => {
    const fetchPage = vi.fn<(window: PageWindow) => Promise<PageResponse<number>>>()
    fetchPage.mockResolvedValueOnce({ items: [1, 2], total: 5, limit: 2, skip: 0 })
    fetchPage.mockResolvedValueOnce({ items: [], total: 5, limit: 2, skip: 2 })

    const result = await fetchAllPages(fetchPage, 2)

    expect(result).toEqual([1, 2])
    expect(fetchPage).toHaveBeenCalledTimes(2)
  })

  it('passes a rejected page through to the caller', async () => {
    const fetchPage = vi
      .fn<(window: PageWindow) => Promise<PageResponse<number>>>()
      .mockRejectedValue(new Error('offline'))

    await expect(fetchAllPages(fetchPage)).rejects.toThrow('offline')
  })
})
