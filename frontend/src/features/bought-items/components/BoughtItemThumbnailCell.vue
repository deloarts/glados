<script setup lang="ts">
import { ItemPictureThumbnail } from '@/shared/pictures'
import { useBoughtItemPicturesStore } from '../stores/boughtItemPicturesStore'

withDefaults(
  defineProps<{ itemId: number; itemName?: string; size?: string; noImageIcon?: string }>(),
  {
    size: '2.5rem',
  },
)

const store = useBoughtItemPicturesStore()
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
