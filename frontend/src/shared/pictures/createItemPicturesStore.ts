import { onScopeDispose, shallowRef, watch } from 'vue'
import { defineStore } from 'pinia'

import { useLiveStore } from '@/core/realtime/liveStore'
import type { LiveSignal } from '@/core/realtime/types'
import type {
  ItemPicture,
  ItemPictureInUse,
  ItemPicturesApi,
  ItemPictureSource,
  ItemPictureVariant,
} from './api'

// The backend caps item_ids at 200 per request.
const MAX_IDS_PER_REQUEST = 200

/**
 * The shape a store built by createItemPicturesStore exposes, so a component
 * can take "some item kind's pictures store" as a prop.
 */
export interface ItemPicturesStoreInstance {
  /** The picture shown for the item, null without one, undefined until fetched. */
  getShown(itemId: number): ItemPictureInUse | null | undefined
  fetchShown(itemId: number): Promise<void>
  /** Every picture of the item, in the order the picture shown is chosen. */
  getPictures(itemId: number): ItemPicture[]
  isLoadingPictures(itemId: number): boolean
  fetchPictures(itemId: number): Promise<void>
  getBlob(itemId: number, source: ItemPictureSource, variant: ItemPictureVariant): Promise<Blob>
  upload(itemId: number, file: File): Promise<ItemPicture>
  removePhoto(itemId: number): Promise<void>
}

/**
 * Builds a Pinia store caching, per item, which picture is shown and the
 * item's full list of pictures. A table of thumbnail cells asks for the
 * picture shown, which leaves in one coalesced request per tick, so a row
 * without a picture costs nothing more. Live signals of `liveResource` and a
 * reconnect reload what is cached, so a picture stored in the background
 * (the Data Portal worker, PDM) appears without a page reload.
 */
export function createItemPicturesStore(
  storeId: string,
  api: ItemPicturesApi,
  liveResource: string,
) {
  return defineStore(storeId, () => {
    // shallowRef: both maps are only ever replaced wholesale.
    const shownByItem = shallowRef<Map<number, ItemPictureInUse | null>>(new Map())
    const picturesByItem = shallowRef<Map<number, ItemPicture[]>>(new Map())
    const loadingPictures = shallowRef<Set<number>>(new Set())

    let inFlight = new Set<number>()
    let pendingIds = new Set<number>()
    let pendingFlush: Promise<void> | null = null

    function getShown(itemId: number): ItemPictureInUse | null | undefined {
      return shownByItem.value.get(itemId)
    }

    async function flushPending(): Promise<void> {
      const ids = [...pendingIds]
      pendingIds = new Set()
      pendingFlush = null
      if (ids.length === 0) return
      try {
        const chunks: number[][] = []
        for (let i = 0; i < ids.length; i += MAX_IDS_PER_REQUEST) {
          chunks.push(ids.slice(i, i + MAX_IDS_PER_REQUEST))
        }
        const results = (await Promise.all(chunks.map((chunk) => api.listInUse(chunk)))).flat()
        const next = new Map(shownByItem.value)
        // Every id asked for is seeded, so an item without a picture caches
        // as null instead of being requested again by the next cell.
        for (const id of ids) next.set(id, null)
        for (const shown of results) next.set(shown.item_id, shown)
        shownByItem.value = next
      } catch {
        // Left uncached for a retry. Swallowed, because callers do not await.
      } finally {
        inFlight = new Set([...inFlight].filter((id) => !ids.includes(id)))
      }
    }

    function queue(itemIds: number[]): Promise<void> {
      for (const id of itemIds) {
        pendingIds.add(id)
        inFlight.add(id)
      }
      pendingFlush ??= Promise.resolve().then(flushPending)
      return pendingFlush
    }

    // Idempotent: an item already cached or in flight is not asked for again.
    async function fetchShown(itemId: number): Promise<void> {
      if (shownByItem.value.has(itemId) || inFlight.has(itemId)) return
      return queue([itemId])
    }

    function getPictures(itemId: number): ItemPicture[] {
      return picturesByItem.value.get(itemId) ?? []
    }

    function isLoadingPictures(itemId: number): boolean {
      return loadingPictures.value.has(itemId)
    }

    async function loadPictures(itemId: number): Promise<void> {
      loadingPictures.value = new Set(loadingPictures.value).add(itemId)
      try {
        const pictures = await api.list(itemId)
        picturesByItem.value = new Map(picturesByItem.value).set(itemId, pictures)
        const shown = pictures.find((p) => p.in_use)
        shownByItem.value = new Map(shownByItem.value).set(
          itemId,
          shown ? { item_id: itemId, picture_id: shown.id, source: shown.source } : null,
        )
      } finally {
        const next = new Set(loadingPictures.value)
        next.delete(itemId)
        loadingPictures.value = next
      }
    }

    async function fetchPictures(itemId: number): Promise<void> {
      if (picturesByItem.value.has(itemId) || loadingPictures.value.has(itemId)) return
      await loadPictures(itemId)
    }

    async function upload(itemId: number, file: File): Promise<ItemPicture> {
      const picture = await api.upload(itemId, file)
      await loadPictures(itemId)
      return picture
    }

    async function removePhoto(itemId: number): Promise<void> {
      await api.removePhoto(itemId)
      await loadPictures(itemId)
    }

    // Reloads in the background; the cache stays until the answer replaces
    // it, so a thumbnail does not blink.
    function reload(itemIds: number[]): void {
      const shown = itemIds.filter((id) => shownByItem.value.has(id))
      if (shown.length > 0) void queue(shown)
      for (const id of itemIds) {
        if (picturesByItem.value.has(id)) void loadPictures(id).catch(() => undefined)
      }
    }

    const live = useLiveStore()
    const unsubscribe = live.on(liveResource, (signal: LiveSignal) => {
      reload(
        signal.action === 'bulk'
          ? [...new Set([...shownByItem.value.keys(), ...picturesByItem.value.keys()])]
          : [signal.id],
      )
    })
    const stopReconnectWatch = watch(
      () => live.reconnectCount,
      () => reload([...new Set([...shownByItem.value.keys(), ...picturesByItem.value.keys()])]),
    )
    onScopeDispose(() => {
      unsubscribe()
      stopReconnectWatch()
    })

    return {
      getShown,
      fetchShown,
      getPictures,
      isLoadingPictures,
      fetchPictures,
      getBlob: api.getBlob,
      upload,
      removePhoto,
    }
  })
}
