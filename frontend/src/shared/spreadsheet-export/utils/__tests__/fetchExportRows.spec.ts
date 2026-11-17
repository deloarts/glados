import { describe, expect, it, vi } from 'vitest'

import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { fetchExportRows } from '../fetchExportRows'

import type { PageResponse } from '@/core/api/types'
import type { PageWindow } from '@/core/api/fetchAllPages'

function listOf(total: number) {
  const rows = Array.from({ length: total }, (_, i) => i + 1)
  return vi.fn<(window: PageWindow, signal: AbortSignal) => Promise<PageResponse<number>>>(
    async ({ skip, limit }) => ({ items: rows.slice(skip, skip + limit), total, skip, limit }),
  )
}

describe('fetchExportRows', () => {
  it('reads consecutive pages at the largest page size until it holds the total', async () => {
    const fetchPage = listOf(API_MAX_PAGE_SIZE * 2 + 3)
    const onProgress = vi.fn<(loaded: number, total: number) => void>()

    const rows = await fetchExportRows(fetchPage, {
      signal: new AbortController().signal,
      onProgress,
    })

    expect(rows).toHaveLength(API_MAX_PAGE_SIZE * 2 + 3)
    expect(fetchPage.mock.calls.map(([window]) => window)).toEqual([
      { skip: 0, limit: API_MAX_PAGE_SIZE },
      { skip: API_MAX_PAGE_SIZE, limit: API_MAX_PAGE_SIZE },
      { skip: API_MAX_PAGE_SIZE * 2, limit: API_MAX_PAGE_SIZE },
    ])
    expect(onProgress).toHaveBeenLastCalledWith(API_MAX_PAGE_SIZE * 2 + 3, API_MAX_PAGE_SIZE * 2 + 3)
  })

  it('stops at maxRows and asks the last page for only the rows it still needs', async () => {
    const fetchPage = listOf(API_MAX_PAGE_SIZE * 3)

    const rows = await fetchExportRows(fetchPage, {
      signal: new AbortController().signal,
      maxRows: API_MAX_PAGE_SIZE + 10,
    })

    expect(rows).toHaveLength(API_MAX_PAGE_SIZE + 10)
    expect(fetchPage).toHaveBeenLastCalledWith(
      { skip: API_MAX_PAGE_SIZE, limit: 10 },
      expect.any(AbortSignal),
    )
  })

  it('ends on a short page when the list shrinks while it is read', async () => {
    const fetchPage = vi.fn<(window: PageWindow) => Promise<PageResponse<number>>>(
      async ({ skip, limit }) => ({ items: skip === 0 ? [1, 2] : [], total: 10, skip, limit }),
    )

    const rows = await fetchExportRows(fetchPage, { signal: new AbortController().signal })

    expect(rows).toEqual([1, 2])
    expect(fetchPage).toHaveBeenCalledTimes(1)
  })

  it('rejects once the signal aborts and reads no further page', async () => {
    const controller = new AbortController()
    const fetchPage = vi.fn<(window: PageWindow) => Promise<PageResponse<number>>>(
      async ({ skip, limit }) => {
        controller.abort()
        return { items: Array.from({ length: limit }, (_, i) => skip + i), total: 5000, skip, limit }
      },
    )

    await expect(fetchExportRows(fetchPage, { signal: controller.signal })).rejects.toMatchObject({
      name: 'AbortError',
    })
    expect(fetchPage).toHaveBeenCalledTimes(1)
  })

  it('passes the signal to every page request so a cancel stops the one in flight', async () => {
    const fetchPage = listOf(3)
    const controller = new AbortController()

    await fetchExportRows(fetchPage, { signal: controller.signal })

    expect(fetchPage.mock.calls[0]?.[1]).toBe(controller.signal)
  })
})
