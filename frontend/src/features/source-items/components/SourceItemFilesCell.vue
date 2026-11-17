<script setup lang="ts">
/** Per-row file icons for a source item: the mesh and PDFs. */
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSourceItemFilesStore } from '../stores/sourceItemFilesStore'
import type { SourceItemFile } from '../types/sourceItemsResponse'

const props = defineProps<{ itemId: number }>()
const emit = defineEmits<{ preview: [file: SourceItemFile] }>()

const { t } = useI18n()
const filesStore = useSourceItemFilesStore()

// Idempotent and coalesced, so both file columns cost one request per tick.
watch(
  () => props.itemId,
  (id) => filesStore.fetchFiles(id),
  { immediate: true },
)

const mesh = computed(() => filesStore.getFiles(props.itemId).find((f) => f.category === 'mesh'))
const pdfs = computed(() => filesStore.getFiles(props.itemId).filter((f) => f.category === 'pdf'))
</script>

<template>
  <div class="source-item-files-cell">
    <i
      v-if="mesh"
      class="mdi mdi-cube-outline files-cell-icon icon-mesh"
      role="button"
      tabindex="0"
      v-tooltip.focus="t('sourceItems.catalogue.files.openFile', { name: mesh.file_name })"
      :aria-label="t('sourceItems.catalogue.files.openFile', { name: mesh.file_name })"
      @click.stop="emit('preview', mesh)"
      @keydown.enter="emit('preview', mesh)"
      @keydown.space.prevent="emit('preview', mesh)"
    />
    <i
      v-for="file in pdfs"
      :key="file.id"
      class="mdi mdi-file-pdf-box files-cell-icon icon-pdf"
      role="button"
      tabindex="0"
      v-tooltip.focus="t('sourceItems.catalogue.files.openFile', { name: file.file_name })"
      :aria-label="t('sourceItems.catalogue.files.openFile', { name: file.file_name })"
      @click.stop="emit('preview', file)"
      @keydown.enter="emit('preview', file)"
      @keydown.space.prevent="emit('preview', file)"
    />
  </div>
</template>

<style scoped lang="scss">
.source-item-files-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: nowrap;
  // Column is sized for a handful of icons; more scrolls rather than wraps.
  overflow-x: auto;
  scrollbar-width: none;
}

.files-cell-icon {
  flex: 0 0 auto;
  font-size: var(--font-size-2xl);
  cursor: pointer;
  color: var(--p-text-muted-color);

  &:hover {
    opacity: 0.75;
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: 2px;
  }
}

.icon-mesh {
  color: var(--p-orange-500);
}

.icon-pdf {
  color: var(--p-red-500);
}
</style>
