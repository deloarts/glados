import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

import { createFilesStore } from '../createFilesStore'
import type { FilesStoreApi } from '../createFilesStore'
import type { LiveSignal } from '@/core/realtime/types'

const liveHandlers = vi.hoisted(() => new Map<string, (signal: LiveSignal) => void>())
const liveState = vi.hoisted(() => ({ reconnectCount: 0 }))

vi.mock('@/core/realtime/liveStore', async () => {
  const { reactive } = await import('vue')
  const state = reactive(liveState)
  return {
    useLiveStore: () => ({
      get reconnectCount() {
        return state.reconnectCount
      },
      on: (resource: string, handler: (signal: LiveSignal) => void) => {
        liveHandlers.set(resource, handler)
        return () => liveHandlers.delete(resource)
      },
    }),
    bumpReconnect: () => state.reconnectCount++,
  }
})

function signal(id: number, action: LiveSignal['action'] = 'updated'): LiveSignal {
  return { resource: 'things', id, action, actor_id: null }
}

interface TestFile {
  id: number
  category: 'main' | 'attachment'
  owner_id: number
}

function makeFile(overrides: Partial<TestFile> = {}): TestFile {
  return { id: 1, category: 'attachment', owner_id: 1, ...overrides }
}

function makeApi(overrides: Partial<FilesStoreApi<TestFile, TestFile['category']>> = {}) {
  return {
    getForItems: vi.fn<(itemIds: number[]) => Promise<TestFile[]>>().mockResolvedValue([]),
    getForItem: vi.fn<(itemId: number) => Promise<TestFile[]>>().mockResolvedValue([]),
    upload: vi.fn<(itemId: number, file: File, category: TestFile['category']) => Promise<TestFile>>(),
    remove: vi.fn<(itemId: number, fileId: number) => Promise<void>>().mockResolvedValue(undefined),
    itemIdOf: (file: TestFile) => file.owner_id,
    singletonCategories: ['main'] as const,
    ...overrides,
  }
}

describe('createFilesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('getFiles/isLoading default to empty/false for an item never fetched', () => {
    const useStore = createFilesStore('filesA', makeApi())
    const store = useStore()

    expect(store.getFiles(1)).toEqual([])
    expect(store.isLoading(1)).toBe(false)
  })

  it('fetchFiles marks the item loading synchronously, then populates it via the bulk endpoint', async () => {
    const api = makeApi({
      getForItems: vi
        .fn<(itemIds: number[]) => Promise<TestFile[]>>()
        .mockResolvedValue([makeFile({ id: 1, owner_id: 1 })]),
    })
    const useStore = createFilesStore('filesB', api)
    const store = useStore()

    const promise = store.fetchFiles(1)
    expect(store.isLoading(1)).toBe(true)

    await promise

    expect(api.getForItems).toHaveBeenCalledWith([1])
    expect(api.getForItem).not.toHaveBeenCalled()
    expect(store.isLoading(1)).toBe(false)
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, owner_id: 1 })])
  })

  it('seeds an item with no files as an empty (cached) array rather than leaving it unfetched', async () => {
    const api = makeApi({ getForItems: vi.fn<(itemIds: number[]) => Promise<TestFile[]>>().mockResolvedValue([]) })
    const useStore = createFilesStore('filesC', api)
    const store = useStore()

    await store.fetchFiles(1)

    expect(store.getFiles(1)).toEqual([])
    // A second fetchFiles must not re-request: the id is now cached.
    await store.fetchFiles(1)
    expect(api.getForItems).toHaveBeenCalledTimes(1)
  })

  it('coalesces fetchFiles calls issued in the same tick into one bulk request', async () => {
    const api = makeApi({
      getForItems: vi.fn<(itemIds: number[]) => Promise<TestFile[]>>().mockResolvedValue([
        makeFile({ id: 1, owner_id: 1 }),
        makeFile({ id: 2, owner_id: 2 }),
      ]),
    })
    const useStore = createFilesStore('filesD', api)
    const store = useStore()

    const p1 = store.fetchFiles(1)
    const p2 = store.fetchFiles(2)
    await Promise.all([p1, p2])

    expect(api.getForItems).toHaveBeenCalledTimes(1)
    expect(api.getForItems).toHaveBeenCalledWith(expect.arrayContaining([1, 2]))
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, owner_id: 1 })])
    expect(store.getFiles(2)).toEqual([makeFile({ id: 2, owner_id: 2 })])
  })

  it('fetchFiles is idempotent for an item already loading - no second request', async () => {
    const api = makeApi({ getForItems: vi.fn<(itemIds: number[]) => Promise<TestFile[]>>().mockResolvedValue([]) })
    const useStore = createFilesStore('filesE', api)
    const store = useStore()

    const p1 = store.fetchFiles(1)
    const p2 = store.fetchFiles(1)
    await Promise.all([p1, p2])

    expect(api.getForItems).toHaveBeenCalledTimes(1)
  })

  it('falls back to one getForItem request per id when no bulk endpoint is configured (e.g. orders)', async () => {
    const api = makeApi({
      getForItems: undefined,
      getForItem: vi
        .fn<(itemId: number) => Promise<TestFile[]>>()
        .mockImplementation((itemId: number) => Promise.resolve([makeFile({ id: itemId, owner_id: itemId })])),
    })
    const useStore = createFilesStore('filesF', api)
    const store = useStore()

    await Promise.all([store.fetchFiles(1), store.fetchFiles(2)])

    expect(api.getForItem).toHaveBeenCalledTimes(2)
    expect(api.getForItem).toHaveBeenCalledWith(1)
    expect(api.getForItem).toHaveBeenCalledWith(2)
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, owner_id: 1 })])
    expect(store.getFiles(2)).toEqual([makeFile({ id: 2, owner_id: 2 })])
  })

  it('chunks a bulk request at 200 ids so a large prefetch never single-shots over the backend cap', async () => {
    const getForItems = vi.fn<(itemIds: number[]) => Promise<TestFile[]>>().mockResolvedValue([])
    const api = makeApi({ getForItems })
    const useStore = createFilesStore('filesG', api)
    const store = useStore()

    // 250 ids requested in the same tick; the coalescing batches them into
    // one flush, which chunks the API call at MAX_IDS_PER_REQUEST (200).
    const ids = Array.from({ length: 250 }, (_, i) => i + 1)
    await Promise.all(ids.map((id) => store.fetchFiles(id)))

    expect(getForItems).toHaveBeenCalledTimes(2)
    const [firstChunk, secondChunk] = getForItems.mock.calls.map((call) => call[0])
    expect(firstChunk).toHaveLength(200)
    expect(secondChunk).toHaveLength(50)
  })

  it('leaves ids uncached on a failed flush so a later render can retry', async () => {
    const getForItems = vi.fn<(itemIds: number[]) => Promise<TestFile[]>>().mockRejectedValue(new Error('500'))
    const api = makeApi({ getForItems })
    const useStore = createFilesStore('filesH', api)
    const store = useStore()

    await store.fetchFiles(1)

    expect(store.isLoading(1)).toBe(false)
    expect(store.getFiles(1)).toEqual([])

    // Retry: since the id was never cached, this issues a fresh request.
    getForItems.mockResolvedValueOnce([makeFile({ id: 1, owner_id: 1 })])
    await store.fetchFiles(1)
    expect(getForItems).toHaveBeenCalledTimes(2)
    expect(store.getFiles(1)).toEqual([makeFile({ id: 1, owner_id: 1 })])
  })

  it('refetchFiles bypasses the cache with a direct getForItem call', async () => {
    const api = makeApi({
      getForItems: vi
        .fn<(itemIds: number[]) => Promise<TestFile[]>>()
        .mockResolvedValue([makeFile({ id: 1, owner_id: 1 })]),
      getForItem: vi
        .fn<(itemId: number) => Promise<TestFile[]>>()
        .mockResolvedValue([makeFile({ id: 1, owner_id: 1 }), makeFile({ id: 2, owner_id: 1 })]),
    })
    const useStore = createFilesStore('filesI', api)
    const store = useStore()

    await store.fetchFiles(1)
    expect(store.getFiles(1)).toHaveLength(1)

    await store.refetchFiles(1)

    expect(api.getForItem).toHaveBeenCalledWith(1)
    expect(store.getFiles(1)).toHaveLength(2)
    expect(store.isLoading(1)).toBe(false)
  })

  it('upload appends the new file to the item cache', async () => {
    const newFile = makeFile({ id: 9, owner_id: 1, category: 'attachment' })
    const api = makeApi({
      upload: vi
        .fn<(itemId: number, file: File, category: TestFile['category']) => Promise<TestFile>>()
        .mockResolvedValue(newFile),
    })
    const useStore = createFilesStore('filesJ', api)
    const store = useStore()
    await store.fetchFiles(1)

    const result = await store.upload(1, new File(['x'], 'a.pdf'), 'attachment')

    expect(result).toBe(newFile)
    expect(store.getFiles(1)).toEqual([newFile])
  })

  it('upload of a singleton category replaces any existing same-category file locally', async () => {
    const oldMain = makeFile({ id: 1, owner_id: 1, category: 'main' })
    const newMain = makeFile({ id: 2, owner_id: 1, category: 'main' })
    const api = makeApi({
      getForItems: vi.fn<(itemIds: number[]) => Promise<TestFile[]>>().mockResolvedValue([oldMain]),
      upload: vi
        .fn<(itemId: number, file: File, category: TestFile['category']) => Promise<TestFile>>()
        .mockResolvedValue(newMain),
    })
    const useStore = createFilesStore('filesK', api)
    const store = useStore()
    await store.fetchFiles(1)
    expect(store.getFiles(1)).toEqual([oldMain])

    await store.upload(1, new File(['x'], 'a.pdf'), 'main')

    expect(store.getFiles(1)).toEqual([newMain])
  })

  it('upload of a non-singleton category appends rather than replaces', async () => {
    const existing = makeFile({ id: 1, owner_id: 1, category: 'attachment' })
    const added = makeFile({ id: 2, owner_id: 1, category: 'attachment' })
    const api = makeApi({
      getForItems: vi.fn<(itemIds: number[]) => Promise<TestFile[]>>().mockResolvedValue([existing]),
      upload: vi
        .fn<(itemId: number, file: File, category: TestFile['category']) => Promise<TestFile>>()
        .mockResolvedValue(added),
    })
    const useStore = createFilesStore('filesL', api)
    const store = useStore()
    await store.fetchFiles(1)

    await store.upload(1, new File(['x'], 'a.pdf'), 'attachment')

    expect(store.getFiles(1)).toEqual([existing, added])
  })

  it('remove calls the API then drops the file from the local cache', async () => {
    const file = makeFile({ id: 1, owner_id: 1 })
    const api = makeApi({
      getForItems: vi.fn<(itemIds: number[]) => Promise<TestFile[]>>().mockResolvedValue([file]),
      remove: vi.fn<(itemId: number, fileId: number) => Promise<void>>().mockResolvedValue(undefined),
    })
    const useStore = createFilesStore('filesM', api)
    const store = useStore()
    await store.fetchFiles(1)

    await store.remove(1, 1)

    expect(api.remove).toHaveBeenCalledWith(1, 1)
    expect(store.getFiles(1)).toEqual([])
  })

  it('invalidate drops an item from the cache so the next fetchFiles re-requests it', async () => {
    const api = makeApi({
      getForItems: vi
        .fn<(itemIds: number[]) => Promise<TestFile[]>>()
        .mockResolvedValue([makeFile({ id: 1, owner_id: 1 })]),
    })
    const useStore = createFilesStore('filesN', api)
    const store = useStore()
    await store.fetchFiles(1)
    expect(api.getForItems).toHaveBeenCalledTimes(1)

    store.invalidate(1)
    expect(store.getFiles(1)).toEqual([])

    await store.fetchFiles(1)
    expect(api.getForItems).toHaveBeenCalledTimes(2)
  })

  describe('with a live resource', () => {
    beforeEach(() => liveHandlers.clear())

    it('reloads a cached item its signal names, keeping the cache until the answer lands', async () => {
      const getForItems = vi.fn<(itemIds: number[]) => Promise<TestFile[]>>()
      getForItems.mockResolvedValueOnce([])
      getForItems.mockResolvedValueOnce([makeFile({ id: 7, category: 'main', owner_id: 1 })])
      const useStore = createFilesStore('filesLiveA', {
        ...makeApi({ getForItems }),
        liveResource: 'things',
      })
      const store = useStore()
      await store.fetchFiles(1)

      liveHandlers.get('things')!(signal(1))
      expect(store.getFiles(1)).toEqual([])
      await flushPromises()

      expect(getForItems).toHaveBeenLastCalledWith([1])
      expect(store.getFiles(1)).toEqual([makeFile({ id: 7, category: 'main', owner_id: 1 })])
    })

    it('ignores a signal for an item it never loaded', async () => {
      const api = makeApi()
      const useStore = createFilesStore('filesLiveB', { ...api, liveResource: 'things' })
      useStore()

      liveHandlers.get('things')!(signal(9))
      await flushPromises()

      expect(api.getForItems).not.toHaveBeenCalled()
    })

    it('reloads every cached item on a bulk signal and after a reconnect, in one request each', async () => {
      const api = makeApi()
      const useStore = createFilesStore('filesLiveC', { ...api, liveResource: 'things' })
      const store = useStore()
      await Promise.all([store.fetchFiles(1), store.fetchFiles(2)])

      liveHandlers.get('things')!(signal(0, 'bulk'))
      await flushPromises()
      expect(api.getForItems).toHaveBeenLastCalledWith([1, 2])

      const { bumpReconnect } = (await import('@/core/realtime/liveStore')) as unknown as {
        bumpReconnect: () => void
      }
      bumpReconnect()
      await flushPromises()
      expect(api.getForItems).toHaveBeenCalledTimes(3)
      expect(api.getForItems).toHaveBeenLastCalledWith([1, 2])
    })

    it('does not subscribe without a live resource', () => {
      const useStore = createFilesStore('filesLiveD', makeApi())
      useStore()

      expect(liveHandlers.size).toBe(0)
    })
  })
})
