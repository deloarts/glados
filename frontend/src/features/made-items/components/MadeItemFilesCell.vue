<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useMadeItemFilesStore } from '../stores/madeItemFilesStore'
import type { MadeItemFile } from '../types/madeItemsResponse'

const props = defineProps<{ itemId: number }>()
const emit = defineEmits<{ preview: [file: MadeItemFile] }>()

const { t } = useI18n()
const filesStore = useMadeItemFilesStore()

// Idempotent and coalesced, the same call MadeItemThumbnailCell makes, so
// a table showing both columns still costs one bulk request per tick.
watch(
  () => props.itemId,
  (id) => filesStore.fetchFiles(id),
  { immediate: true },
)

const drawing = computed(() =>
  filesStore.getFiles(props.itemId).find((f) => f.category === 'drawing'),
)
const dxf = computed(() => filesStore.getFiles(props.itemId).find((f) => f.category === 'dxf'))
const pdfs = computed(() => filesStore.getFiles(props.itemId).filter((f) => f.category === 'pdf'))
</script>

<template>
  <div class="made-item-files-cell">
    <i
      v-if="drawing"
      class="mdi mdi-file-pdf-box files-cell-icon icon-drawing"
      role="button"
      tabindex="0"
      v-tooltip.focus="t('madeItems.catalogue.files.openFile', { name: drawing.file_name })"
      :aria-label="t('madeItems.catalogue.files.openFile', { name: drawing.file_name })"
      @click.stop="emit('preview', drawing)"
      @keydown.enter="emit('preview', drawing)"
      @keydown.space.prevent="emit('preview', drawing)"
    />
    <i
      v-if="dxf"
      class="mdi mdi-vector-square files-cell-icon icon-dxf"
      role="button"
      tabindex="0"
      v-tooltip.focus="t('madeItems.catalogue.files.openFile', { name: dxf.file_name })"
      :aria-label="t('madeItems.catalogue.files.openFile', { name: dxf.file_name })"
      @click.stop="emit('preview', dxf)"
      @keydown.enter="emit('preview', dxf)"
      @keydown.space.prevent="emit('preview', dxf)"
    />
    <i
      v-for="file in pdfs"
      :key="file.id"
      class="mdi mdi-file-pdf-box files-cell-icon icon-pdf"
      role="button"
      tabindex="0"
      v-tooltip.focus="t('madeItems.catalogue.files.openFile', { name: file.file_name })"
      :aria-label="t('madeItems.catalogue.files.openFile', { name: file.file_name })"
      @click.stop="emit('preview', file)"
      @keydown.enter="emit('preview', file)"
      @keydown.space.prevent="emit('preview', file)"
    />
  </div>
</template>

<style scoped lang="scss">
.made-item-files-cell {
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

.icon-drawing,
.icon-pdf {
  color: var(--p-red-500);
}

.icon-dxf {
  color: var(--p-green-600);
}
</style>
