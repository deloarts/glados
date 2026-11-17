import { onScopeDispose, shallowRef, watch } from 'vue'
import { defineStore } from 'pinia'

import { useLiveStore } from '@/core/realtime/liveStore'

import type { LiveSignal } from '@/core/realtime/types'

// The backend caps item_ids at 200 per request; a page can't currently
// reach that, but chunking here keeps a caller that prefetches a big list
// from silently 422-ing.
const MAX_IDS_PER_REQUEST = 200

/**
 * The minimum shape a per-entity file record must have for this store to
 * bucket it. Each feature's own file type is a superset.
 */
interface FileRecord<TCategory extends string> {
  id: number
  category: TCategory
}

/**
 * The shape a store built by createFilesStore exposes. Lets a component take
 * "some entity's files store" as a prop without knowing which entity.
 */
export interface FilesStoreInstance<TFile extends FileRecord<TCategory>, TCategory extends string> {
  getFiles(itemId: number): TFile[]
  isLoading(itemId: number): boolean
  fetchFiles(itemId: number): Promise<void>
  refetchFiles(itemId: number): Promise<void>
  upload(itemId: number, file: File, category: TCategory): Promise<TFile>
  remove(itemId: number, fileId: number): Promise<void>
  invalidate(itemId: number): void
}

export interface FilesStoreApi<TFile extends FileRecord<TCategory>, TCategory extends string> {
  /**
   * Files for many items at once: the one request the coalescing exists for.
   * Omit for entities with no bulk endpoint (orders); the store then falls
   * back to one request per id, which is why every entity that renders a
   * table of thumbnails should have one.
   */
  getForItems?(itemIds: number[]): Promise<TFile[]>
  /** Files for a single item, bypassing the cache. */
  getForItem(itemId: number): Promise<TFile[]>
  upload(itemId: number, file: File, category: TCategory): Promise<TFile>
  remove(itemId: number, fileId: number): Promise<void>
  /**
   * Reads the owning item's id off a file record; the column name differs
   * per entity (bought_item_id, made_item_id, ...).
   */
  itemIdOf(file: TFile): number
  /**
   * Categories the backend replaces rather than appends, so the local cache
   * can drop the superseded record without a refetch.
   */
  singletonCategories: readonly TCategory[]
  /**
   * The live resource whose signals name an item whose files changed on
   * the server, such as a picture stored in the background. Cached items it
   * names are reloaded, so their thumbnails follow without a page reload.
   */
  liveResource?: string
}

/**
 * Builds a Pinia store caching an entity's file attachments per item, so a
 * table of thumbnail cells costs one coalesced request instead of one per
 * row.
 */
export function createFilesStore<TFile extends FileRecord<TCategory>, TCategory extends string>(
  storeId: string,
  api: FilesStoreApi<TFile, TCategory>,
) {
  return defineStore(storeId, () => {
    // shallowRef, not ref: both are only ever replaced wholesale, and a deep
    // ref would try to unwrap the generic file records it holds.
    const filesByItem = shallowRef<Map<number, TFile[]>>(new Map())
    const loadingItems = shallowRef<Set<number>>(new Set())

    // Ids requested in the same tick leave together as one bulk request.
    let pendingIds = new Set<number>()
    let pendingFlush: Promise<void> | null = null

    function getFiles(itemId: number): TFile[] {
      return filesByItem.value.get(itemId) ?? []
    }

    function isLoading(itemId: number): boolean {
      return loadingItems.value.has(itemId)
    }

    function setLoading(ids: number[], loading: boolean): void {
      const next = new Set(loadingItems.value)
      for (const id of ids) {
        if (loading) next.add(id)
        else next.delete(id)
      }
      loadingItems.value = next
    }

    async function flushPending(): Promise<void> {
      const ids = [...pendingIds]
      pendingIds = new Set()
      pendingFlush = null
      if (ids.length === 0) return

      try {
        let results: TFile[][]
        if (api.getForItems) {
          const chunks: number[][] = []
          for (let i = 0; i < ids.length; i += MAX_IDS_PER_REQUEST) {
            chunks.push(ids.slice(i, i + MAX_IDS_PER_REQUEST))
          }
          results = await Promise.all(chunks.map((chunk) => api.getForItems!(chunk)))
        } else {
          // No bulk endpoint: one request per id. Still coalesced into a
          // single flush, so the caching and seeding below behave the same.
          results = await Promise.all(ids.map((id) => api.getForItem(id)))
        }

        const next = new Map(filesByItem.value)
        // Seed every id that was asked for, so an item with no files caches
        // as an empty list instead of looking unfetched and being requested
        // again by the next component that renders it.
        for (const id of ids) next.set(id, [])
        for (const file of results.flat()) {
          next.get(api.itemIdOf(file))?.push(file)
        }
        filesByItem.value = next
      } catch {
        // Left uncached for a retry. Swallowed, because callers do not await.
      } finally {
        setLoading(ids, false)
      }
    }

    // Idempotent: returns immediately for an item already loaded or already
    // in flight, so components can call it freely on every mount.
    async function fetchFiles(itemId: number): Promise<void> {
      if (filesByItem.value.has(itemId) || loadingItems.value.has(itemId)) return
      setLoading([itemId], true)
      pendingIds.add(itemId)
      pendingFlush ??= Promise.resolve().then(flushPending)
      return pendingFlush
    }

    // Bypasses the cache: for the one place that must see server state it
    // may have just changed out-of-band (the files section after an upload
    // that went through another client).
    async function refetchFiles(itemId: number): Promise<void> {
      setLoading([itemId], true)
      try {
        filesByItem.value = new Map(filesByItem.value).set(itemId, await api.getForItem(itemId))
      } finally {
        setLoading([itemId], false)
      }
    }

    async function upload(itemId: number, file: File, category: TCategory): Promise<TFile> {
      const newFile = await api.upload(itemId, file, category)
      const current = filesByItem.value.get(itemId) ?? []
      // Singleton categories: backend replaces server-side, remove old
      // same-category file locally.
      const filtered = api.singletonCategories.includes(category)
        ? current.filter((f) => f.category !== category)
        : current
      filesByItem.value = new Map(filesByItem.value).set(itemId, [...filtered, newFile])
      return newFile
    }

    async function remove(itemId: number, fileId: number): Promise<void> {
      await api.remove(itemId, fileId)
      const current = filesByItem.value.get(itemId) ?? []
      filesByItem.value = new Map(filesByItem.value).set(
        itemId,
        current.filter((f) => f.id !== fileId),
      )
    }

    // Reloads cached items in the background: the cache stays as it is until
    // the answer replaces it, so a thumbnail does not blink while it loads.
    function reload(itemIds: number[]): void {
      const cached = itemIds.filter((id) => filesByItem.value.has(id))
      if (cached.length === 0) return
      for (const id of cached) pendingIds.add(id)
      pendingFlush ??= Promise.resolve().then(flushPending)
    }

    if (api.liveResource) {
      const live = useLiveStore()
      const unsubscribe = live.on(api.liveResource, (signal: LiveSignal) => {
        reload(signal.action === 'bulk' ? [...filesByItem.value.keys()] : [signal.id])
      })
      // Whatever changed while the connection was down is caught up here.
      const stopReconnectWatch = watch(
        () => live.reconnectCount,
        () => reload([...filesByItem.value.keys()]),
      )
      onScopeDispose(() => {
        unsubscribe()
        stopReconnectWatch()
      })
    }

    function invalidate(itemId: number): void {
      const next = new Map(filesByItem.value)
      next.delete(itemId)
      filesByItem.value = next
    }

    return { getFiles, isLoading, fetchFiles, refetchFiles, upload, remove, invalidate }
  })
}
