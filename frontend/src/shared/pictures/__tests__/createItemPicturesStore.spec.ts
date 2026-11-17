import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

import { createItemPicturesStore } from '../createItemPicturesStore'
import type { ItemPicture, ItemPictureInUse, ItemPicturesApi } from '../api'
import type { LiveSignal } from '@/core/realtime/types'

const liveHandlers = vi.hoisted(() => new Map<string, (signal: LiveSignal) => void>())

vi.mock('@/core/realtime/liveStore', async () => {
  const { reactive } = await import('vue')
  const state = reactive({ reconnectCount: 0 })
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
  }
})

function picture(overrides: Partial<ItemPicture> = {}): ItemPicture {
  return {
    id: 1,
    public_id: '00000000-0000-0000-0000-000000000001',
    item_id: 1,
    source: 'picture',
    file_name: 'photo.jpg',
    has_image: true,
    has_thumbnail: true,
    created: '2026-10-29T00:00:00Z',
    uploaded_by_user_id: 1,
    in_use: true,
    ...overrides,
  }
}

function makeApi() {
  return {
    list: vi.fn<(itemId: number) => Promise<ItemPicture[]>>().mockResolvedValue([]),
    listInUse: vi
      .fn<(itemIds: number[]) => Promise<ItemPictureInUse[]>>()
      .mockResolvedValue([]),
    getBlob: vi.fn<ItemPicturesApi['getBlob']>().mockResolvedValue(new Blob(['x'])),
    upload: vi.fn<ItemPicturesApi['upload']>().mockResolvedValue(picture()),
    removePhoto: vi.fn<(itemId: number) => Promise<void>>().mockResolvedValue(undefined),
  }
}

describe('createItemPicturesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    liveHandlers.clear()
  })

  it('asks for the pictures shown of one tick in one request and caches a missing one as null', async () => {
    const api = makeApi()
    api.listInUse.mockResolvedValue([{ item_id: 1, picture_id: 7, source: 'cad_rendering' }])
    const store = createItemPicturesStore('pictures-a', api, 'things')()

    void store.fetchShown(1)
    void store.fetchShown(2)
    await flushPromises()
    void store.fetchShown(2)
    await flushPromises()

    expect(api.listInUse).toHaveBeenCalledTimes(1)
    expect(api.listInUse).toHaveBeenCalledWith([1, 2])
    expect(store.getShown(1)?.source).toBe('cad_rendering')
    expect(store.getShown(2)).toBeNull()
  })

  it('updates the picture shown after an upload', async () => {
    const api = makeApi()
    api.list.mockResolvedValue([picture({ id: 9 }), picture({ id: 3, source: 'cad_rendering', in_use: false })])
    const store = createItemPicturesStore('pictures-b', api, 'things')()

    await store.upload(1, new File(['x'], 'photo.jpg'))

    expect(store.getPictures(1).map((p) => p.id)).toEqual([9, 3])
    expect(store.getShown(1)).toEqual({ item_id: 1, picture_id: 9, source: 'picture' })
  })

  it('reloads a cached item named by a live signal', async () => {
    const api = makeApi()
    const store = createItemPicturesStore('pictures-c', api, 'things')()
    await store.fetchShown(4)
    expect(store.getShown(4)).toBeNull()

    api.listInUse.mockResolvedValue([{ item_id: 4, picture_id: 2, source: 'data_portal' }])
    liveHandlers.get('things')?.({ resource: 'things', id: 4, action: 'updated', actor_id: null })
    await flushPromises()

    expect(store.getShown(4)?.source).toBe('data_portal')
  })
})
