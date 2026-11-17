import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import axios from 'axios'

import type { MadeItemChangelogEntry } from '../../types/madeItemsChangelogResponse'
import type { MadeItemResponse } from '../../types/madeItemsResponse'

const getMadeItemChangelogMock = vi.fn<(itemId: number) => Promise<MadeItemChangelogEntry[]>>()

vi.mock('../../api/getMadeItemChangelog', () => ({
  getMadeItemChangelog: (itemId: number) => getMadeItemChangelogMock(itemId),
}))

import { useMadeItemsChangelogStore } from '../madeItemsChangelogStore'

function makeItem(overrides: Partial<MadeItemResponse> = {}): MadeItemResponse {
  return { id: 1, article_name: 'Widget', ...overrides } as unknown as MadeItemResponse
}

function makeEntry(overrides: Partial<MadeItemChangelogEntry> = {}): MadeItemChangelogEntry {
  return { timestamp: '2026-01-01T00:00:00Z', username: 'ada', message: 'Created', ...overrides }
}

describe('useMadeItemsChangelogStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getMadeItemChangelogMock.mockReset()
  })

  it('starts with no selected item, no entries, and loading false', () => {
    const store = useMadeItemsChangelogStore()
    expect(store.loading).toBe(false)
    expect(store.selectedItem).toBeNull()
    expect(store.entries).toEqual([])
  })

  it('selecting an item fetches its changelog entries', async () => {
    const entries = [makeEntry({ message: 'Created' }), makeEntry({ message: 'Renamed' })]
    getMadeItemChangelogMock.mockResolvedValue(entries)
    const store = useMadeItemsChangelogStore()

    store.selectedItem = makeItem({ id: 7 })
    await flushPromises()

    expect(getMadeItemChangelogMock).toHaveBeenCalledWith(7)
    expect(store.entries).toEqual(entries)
    expect(store.loading).toBe(false)
  })

  it('sets loading true while the fetch is in flight', async () => {
    let resolveFetch!: (entries: MadeItemChangelogEntry[]) => void
    getMadeItemChangelogMock.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve
      }),
    )
    const store = useMadeItemsChangelogStore()

    store.selectedItem = makeItem({ id: 1 })
    await flushPromises()
    expect(store.loading).toBe(true)

    resolveFetch([makeEntry()])
    await flushPromises()
    expect(store.loading).toBe(false)
  })

  it('switching to a different item clears entries immediately, before the new fetch resolves', async () => {
    getMadeItemChangelogMock.mockResolvedValueOnce([makeEntry({ message: 'first' })])
    const store = useMadeItemsChangelogStore()
    store.selectedItem = makeItem({ id: 1 })
    await flushPromises()
    expect(store.entries).toHaveLength(1)

    let resolveSecond!: (entries: MadeItemChangelogEntry[]) => void
    getMadeItemChangelogMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveSecond = resolve
      }),
    )
    store.selectedItem = makeItem({ id: 2 })
    await flushPromises()

    expect(store.entries).toEqual([])

    resolveSecond([makeEntry({ message: 'second' })])
    await flushPromises()
    expect(store.entries).toEqual([makeEntry({ message: 'second' })])
  })

  it('clearing the selection (null) resets entries without calling the API', async () => {
    getMadeItemChangelogMock.mockResolvedValueOnce([makeEntry()])
    const store = useMadeItemsChangelogStore()
    store.selectedItem = makeItem({ id: 1 })
    await flushPromises()
    expect(store.entries).toHaveLength(1)
    getMadeItemChangelogMock.mockClear()

    store.selectedItem = null
    await flushPromises()

    expect(store.entries).toEqual([])
    expect(getMadeItemChangelogMock).not.toHaveBeenCalled()
  })

  it('a rejected getMadeItemChangelog call sets error instead of throwing', async () => {
    const axiosError = Object.assign(new Error('Request failed'), {
      isAxiosError: true,
      response: { data: { detail: 'Internal Server Error' } },
    })
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)
    getMadeItemChangelogMock.mockRejectedValue(axiosError)
    const store = useMadeItemsChangelogStore()

    store.selectedItem = makeItem({ id: 1 })
    await flushPromises()

    expect(store.entries).toEqual([])
    expect(store.loading).toBe(false)
    expect(store.error).toBe('Internal Server Error')
  })

  it('clear() resets selectedItem and entries', async () => {
    getMadeItemChangelogMock.mockResolvedValueOnce([makeEntry()])
    const store = useMadeItemsChangelogStore()
    store.selectedItem = makeItem({ id: 1 })
    await flushPromises()

    store.clear()

    expect(store.selectedItem).toBeNull()
    expect(store.entries).toEqual([])
  })
})
