<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'
import { useThumbnailSrc } from '@/core/composables/useThumbnailSrc'
import { useHostStore } from '@/core/host/stores/hostStore'
import { getProductFileBlob } from '../api/getProductFileBlob'
import { useProductFilesStore } from '../stores/productFilesStore'
import type { ProductFile } from '../types/productResponse'

/**
 * The product's picture for an overview tab: its image, or its thumbnail
 * when it has no image, framed and scaled to fit. A click opens the file in
 * full size. Without either file, or without file storage, nothing renders.
 */

const props = defineProps<{
  productId: number
  productNumber: string
}>()

const { t } = useI18n()
const hostStore = useHostStore()
const filesStore = useProductFilesStore()

function pickPicture(files: ProductFile[]): ProductFile | undefined {
  return files.find((f) => f.category === 'image') ?? files.find((f) => f.category === 'thumbnail')
}

const file = computed(() => pickPicture(filesStore.getFiles(props.productId)))

const src = useThumbnailSrc({
  itemId: () => props.productId,
  files: (id) => filesStore.getFiles(id),
  fetchFiles: (id) => (hostStore.storageEnabled ? filesStore.fetchFiles(id) : undefined),
  fetchBlob: getProductFileBlob,
  pick: pickPicture,
})

const previewVisible = ref(false)

function fetchFull(): Promise<Blob> {
  return getProductFileBlob(props.productId, file.value!.id)
}
</script>

<template>
  <template v-if="hostStore.storageEnabled && file">
    <button
      v-tooltip.bottom="t('resources.products.picture.open', { name: file.file_name })"
      type="button"
      class="product-picture"
      :aria-label="t('resources.products.picture.open', { name: file.file_name })"
      data-testid="product-picture"
      @click="previewVisible = true"
    >
      <img v-if="src" :src="src" :alt="productNumber" class="picture-img" />
      <span class="picture-hint" aria-hidden="true">
        <i class="mdi mdi-arrow-expand" />
        {{ t('resources.products.picture.fullSize') }}
      </span>
    </button>

    <FilePreviewDialog
      v-model:visible="previewVisible"
      :filename="file.file_name"
      :mime-type="file.mime_type"
      :fetch-blob="fetchFull"
    />
  </template>
</template>

<style scoped lang="scss">
.product-picture {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 22rem;
  padding: var(--space-4);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  background: var(--p-content-hover-background);
  cursor: pointer;
  font: inherit;
  color: inherit;

  &:hover {
    border-color: var(--p-primary-color);

    .picture-hint {
      opacity: 1;
    }
  }

  &:focus-visible {
    outline: 2px solid var(--p-primary-color);
    outline-offset: 2px;
  }
}

.picture-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.picture-hint {
  position: absolute;
  right: 0.6rem;
  bottom: 0.6rem;
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  font-size: var(--font-size-xs);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-sm);
  background: var(--p-content-background);
  opacity: 0;
  transition: opacity 0.15s;
}
</style>
