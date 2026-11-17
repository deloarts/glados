<script setup lang="ts">
import { computed } from 'vue'

import { ItemPictureThumbnail } from '@/shared/pictures'
import { useSourceItemPicturesStore } from '../stores/sourceItemPicturesStore'
import { sourceItemPlaceholder } from '../utils/sourceItemPlaceholder'

const props = withDefaults(
  defineProps<{
    itemId: number
    itemName?: string
    size?: string
    noImageIcon?: string
    /**
     * The item's dimension string. When it has no picture, a
     * shape-appropriate placeholder is shown instead (see
     * sourceItemPlaceholder.ts). A custom/unrecognised/empty dimension gets
     * no placeholder, same as omitting this prop.
     */
    dimension?: string | null
  }>(),
  {
    size: '2.5rem',
  },
)

const store = useSourceItemPicturesStore()

const placeholder = computed(() => sourceItemPlaceholder(props.dimension)?.image ?? null)
</script>

<template>
  <ItemPictureThumbnail
    :store="store"
    :item-id="itemId"
    :item-name="itemName"
    :size="size"
    :no-image-icon="noImageIcon"
    :fallback-src="placeholder"
  />
</template>
