import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

import { LiveResource } from '@/core/realtime/resources'
import type { LiveSignal } from '@/core/realtime/types'
import type { MadeItemFile } from '../../types/madeItemsResponse'

const liveHandlers = vi.hoisted(() => new Map<string, (signal: LiveSignal) => void>())
const getForItemsMock = vi.fn<(itemIds: number[]) => Promise<MadeItemFile[]>>()

vi.mock('@/core/realtime/liveStore', () => ({
  useLiveStore: () => ({
    reconnectCount: 0,
    on: (resource: string, handler: (signal: LiveSignal) => void) => {
      liveHandlers.set(resource, handler)
      return () => liveHandlers.delete(resource)
    },
  }),
}))

vi.mock('../../api/madeItemFilesApi', () => ({
  getMadeItemFilesForItems: (itemIds: number[]) => getForItemsMock(itemIds),
  getMadeItemFiles: vi.fn<() => Promise<MadeItemFile[]>>(),
  uploadMadeItemFile: vi.fn<() => Promise<MadeItemFile>>(),
  deleteMadeItemFile: vi.fn<() => Promise<void>>(),
}))

import { useMadeItemFilesStore } from '../madeItemFilesStore'

function makeMesh(): MadeItemFile {
  return {
    id: 5,
    public_id: '55555555-5555-5555-5555-555555555555',
    made_item_id: 1,
    file_name: 'part.stl',
    stored_name: 'stored-part.stl',
    mime_type: 'model/stl',
    size_bytes: 2048,
    storage_path: '/files/stored-part.stl',
    sha256: 'deadbeef',
    category: 'mesh',
    created: '2026-11-27T00:00:00Z',
    uploaded_by_user_id: 1,
    url: null,
    from_pdm: true,
  }
}

describe('useMadeItemFilesStore live sync', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    liveHandlers.clear()
    getForItemsMock.mockReset()
  })

  it('shows a mesh stored elsewhere on an open item without a reload', async () => {
    getForItemsMock.mockResolvedValueOnce([])
    getForItemsMock.mockResolvedValueOnce([makeMesh()])
    const store = useMadeItemFilesStore()
    await store.fetchFiles(1)

    const signal: LiveSignal = {
      resource: LiveResource.MADE_ITEMS,
      id: 1,
      action: 'updated',
      actor_id: null,
    }
    liveHandlers.get(LiveResource.MADE_ITEMS)!(signal)
    await flushPromises()

    expect(getForItemsMock).toHaveBeenLastCalledWith([1])
    expect(store.getFiles(1)).toEqual([makeMesh()])
  })
})
