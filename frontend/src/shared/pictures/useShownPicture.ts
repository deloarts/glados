import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import type { ItemPicturesStoreInstance } from './createItemPicturesStore'

/** The picture shown for an item, as a detail page opens it full size. */
export interface ShownPicture {
  /** Changes whenever another picture becomes the one shown. */
  id: number
  /** The picture's source, worded for a preview dialog's title. */
  name: string
  fetchImage: () => Promise<Blob>
}

/**
 * The picture shown for the item `itemId` names (the photo, else the Data
 * Portal picture, else the CAD rendering), fetched through the kind's
 * pictures store; null while the item has none or none is loaded.
 */
export function useShownPicture(store: ItemPicturesStoreInstance, itemId: () => number | null) {
  const { t } = useI18n()

  watch(
    itemId,
    (id) => {
      if (id !== null) void store.fetchShown(id)
    },
    { immediate: true },
  )

  return computed<ShownPicture | null>(() => {
    const id = itemId()
    const shown = id === null ? null : store.getShown(id)
    if (id === null || !shown) return null
    return {
      id: shown.picture_id,
      name: t(`common.pictures.sources.${shown.source}`),
      fetchImage: () => store.getBlob(id, shown.source, 'image'),
    }
  })
}
