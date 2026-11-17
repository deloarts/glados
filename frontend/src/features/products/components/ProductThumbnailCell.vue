<script setup lang="ts">
import ThumbnailCell from '@/core/components/ThumbnailCell.vue'
import { useThumbnailSrc } from '@/core/composables/useThumbnailSrc'
import { getProductFileBlob } from '../api/getProductFileBlob'
import { useProductFilesStore } from '../stores/productFilesStore'

const props = withDefaults(
  defineProps<{ itemId: number; itemName?: string; size?: string; noImageIcon?: string }>(),
  {
    size: '2.5rem',
  },
)

const filesStore = useProductFilesStore()

const imgSrc = useThumbnailSrc({
  itemId: () => props.itemId,
  files: (id) => filesStore.getFiles(id),
  fetchFiles: (id) => filesStore.fetchFiles(id),
  fetchBlob: getProductFileBlob,
})
</script>

<template>
  <ThumbnailCell :src="imgSrc" :item-name="itemName" :size="size" :no-image-icon="noImageIcon" />
</template>
