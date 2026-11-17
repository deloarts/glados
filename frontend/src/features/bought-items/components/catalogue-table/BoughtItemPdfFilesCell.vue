<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { BoughtItemPdfFile, BoughtItemResponse } from '../../types/boughtItemsResponse'

defineProps<{
  item: BoughtItemResponse
}>()

const emit = defineEmits<{
  'open-pdf': [file: BoughtItemPdfFile]
}>()

const { t } = useI18n()
</script>

<template>
  <div class="pdf-files-cell">
    <i
      v-for="file in item.pdf_files"
      :key="file.id"
      class="mdi mdi-file-pdf-box pdf-file-icon"
      role="button"
      tabindex="0"
      v-tooltip.focus="t('boughtItems.catalogue.files.openPdf', { name: file.file_name })"
      :aria-label="t('boughtItems.catalogue.files.openPdf', { name: file.file_name })"
      @click.stop="emit('open-pdf', file)"
      @keydown.enter="emit('open-pdf', file)"
      @keydown.space.prevent="emit('open-pdf', file)"
    />
  </div>
</template>

<style scoped lang="scss">
.pdf-files-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: nowrap;
  // Column is sized for ~4 icons; an item with more scrolls rather than wraps.
  overflow-x: auto;
  scrollbar-width: none;
}

.pdf-file-icon {
  flex: 0 0 auto;
  font-size: var(--font-size-2xl);
  color: var(--p-text-muted-color);
  cursor: pointer;

  &:hover {
    color: var(--p-primary-color);
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: 2px;
  }
}
</style>
