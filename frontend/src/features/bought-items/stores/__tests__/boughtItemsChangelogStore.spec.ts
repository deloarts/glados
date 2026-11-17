import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import axios from 'axios'

import type { BoughtItemChangelogEntry } from '../../types/boughtItemsChangelogResponse'
import type { BoughtItemResponse } from '../../types/boughtItemsResponse'

const getChangelogMock = vi.fn<(itemId: number) => Promise<BoughtItemChangelogEntry[]>>()

vi.mock('../../api/getBoughtItemChangelog', () => ({
  getBoughtItemChangelog: (itemId: number) => getChangelogMock(itemId),
}))

import { useBoughtItemsChangelogStore } from '../boughtItemsChangelogStore'

function makeItem(overrides: Partial<BoughtItemResponse> = {}): BoughtItemResponse {
  return { id: 1, article_name: 'Widget', ...overrides } as unknown as BoughtItemResponse
}

function makeEntry(overrides: Partial<BoughtItemChangelogEntry> = {}): BoughtItemChangelogEntry {
  return {
    timestamp: '2026-09-01 10:00:00',
    username: 'sam',
    message: 'changed article_name from "Old" to "Widget"',
    ...overrides,
  }
}

// selectedItem drives a watcher rather than an explicit fetch action, so
// every case here sets selectedItem and awaits flushPromises() to let the
// watcher's async body settle.
describe('useBoughtItemsChangelogStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getChangelogMock.mockReset()
  })

  it('starts with no selected item, no entries, and loading off', () => {
    const store = useBoughtItemsChangelogStore()
    expect(store.selectedItem).toBeNull()
    expect(store.entries).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('selecting an item fetches its changelog and populates entries', async () => {
    getChangelogMock.mockResolvedValue([makeEntry()])
    const store = useBoughtItemsChangelogStore()

    store.selectedItem = makeItem({ id: 7 })
    await flushPromises()

    expect(getChangelogMock).toHaveBeenCalledWith(7)
    expect(store.entries).toEqual([makeEntry()])
    expect(store.loading).toBe(false)
  })

  it('loading is true while the changelog request is in flight', async () => {
    let resolveFetch!: (entries: BoughtItemChangelogEntry[]) => void
    getChangelogMock.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve
      }),
    )
    const store = useBoughtItemsChangelogStore()

    store.selectedItem = makeItem({ id: 7 })
    await flushPromises()
    expect(store.loading).toBe(true)

    resolveFetch([makeEntry()])
    await flushPromises()
    expect(store.loading).toBe(false)
    expect(store.entries).toEqual([makeEntry()])
  })

  it('selecting a new item resets entries before the new changelog arrives', async () => {
    getChangelogMock.mockResolvedValueOnce([makeEntry()])
    const store = useBoughtItemsChangelogStore()
    store.selectedItem = makeItem({ id: 7 })
    await flushPromises()
    expect(store.entries).toHaveLength(1)

    let resolveSecond!: (entries: BoughtItemChangelogEntry[]) => void
    getChangelogMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveSecond = resolve
      }),
    )
    store.selectedItem = makeItem({ id: 8 })
    await flushPromises()

    expect(store.entries).toEqual([])
    resolveSecond([makeEntry({ username: 'other' })])
    await flushPromises()
    expect(store.entries).toEqual([makeEntry({ username: 'other' })])
  })

  it('deselecting (setting selectedItem to null) clears entries and does not fetch', async () => {
    getChangelogMock.mockResolvedValue([makeEntry()])
    const store = useBoughtItemsChangelogStore()
    store.selectedItem = makeItem({ id: 7 })
    await flushPromises()
    expect(store.entries).toHaveLength(1)

    store.selectedItem = null
    await flushPromises()

    expect(store.entries).toEqual([])
    expect(getChangelogMock).toHaveBeenCalledTimes(1)
  })

  it('a failed changelog fetch sets error instead of throwing', async () => {
    const axiosError = Object.assign(new Error('Request failed'), {
      isAxiosError: true,
      response: { data: { detail: 'Internal Server Error' } },
    })
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)
    getChangelogMock.mockRejectedValue(axiosError)
    const store = useBoughtItemsChangelogStore()

    store.selectedItem = makeItem({ id: 7 })
    await flushPromises()

    expect(store.entries).toEqual([])
    expect(store.loading).toBe(false)
    expect(store.error).toBe('Internal Server Error')
  })

  it('clear resets selectedItem and entries', async () => {
    getChangelogMock.mockResolvedValue([makeEntry()])
    const store = useBoughtItemsChangelogStore()
    store.selectedItem = makeItem({ id: 7 })
    await flushPromises()

    store.clear()

    expect(store.selectedItem).toBeNull()
    expect(store.entries).toEqual([])
  })
})
