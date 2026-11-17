<script setup lang="ts">
import { ItemPictureThumbnail } from '@/shared/pictures'
import { useMadeItemPicturesStore } from '../stores/madeItemPicturesStore'

withDefaults(
  defineProps<{ itemId: number; itemName?: string; size?: string; noImageIcon?: string }>(),
  {
    size: '2.5rem',
  },
)

const store = useMadeItemPicturesStore()
</script>

<template>
  <ItemPictureThumbnail
    :store="store"
    :item-id="itemId"
    :item-name="itemName"
    :size="size"
    :no-image-icon="noImageIcon"
  />
</template>
