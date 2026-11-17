<script setup lang="ts">
/**
 * The picture shown for an item (the photo, else the Data Portal picture,
 * else the CAD rendering) as a fixed-size square, for table cells and the
 * Item card of a detail page. Each kind's thumbnail cell binds its own
 * pictures store; a row without a picture requests no image at all.
 */
import { watch } from 'vue'

import ThumbnailCell from '@/core/components/ThumbnailCell.vue'
import { useBlobObjectUrl } from '@/shared/composables/useBlobObjectUrl'

import type { ItemPictureVariant } from './api'
import type { ItemPicturesStoreInstance } from './createItemPicturesStore'

const props = withDefaults(
  defineProps<{
    store: ItemPicturesStoreInstance
    itemId: number
    itemName?: string
    size?: string
    noImageIcon?: string
    variant?: ItemPictureVariant
    /** Shown while the item has no picture, such as a stock shape sketch. */
    fallbackSrc?: string | null
  }>(),
  { size: '2.5rem', variant: 'thumbnail' },
)

// Watched rather than called once, since a table row can be recycled onto
// a different item without remounting this component.
watch(
  () => props.itemId,
  (id) => void props.store.fetchShown(id),
  { immediate: true },
)

// The picture id changes whenever the picture shown changes, so it keys the
// download: an equal answer after a live reload fetches nothing again.
const { url } = useBlobObjectUrl(
  () => {
    const shown = props.store.getShown(props.itemId)
    return shown ? `${props.itemId}:${shown.source}:${shown.picture_id}:${props.variant}` : null
  },
  (key) => {
    const [itemId, source] = key.split(':')
    return props.store.getBlob(
      Number(itemId),
      source as Parameters<ItemPicturesStoreInstance['getBlob']>[1],
      props.variant,
    )
  },
  'image/png',
)
</script>

<template>
  <ThumbnailCell
    :src="url ?? fallbackSrc ?? null"
    :item-name="itemName"
    :size="size"
    :no-image-icon="noImageIcon"
  />
</template>
