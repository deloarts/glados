<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { QaEvidenceFile } from '../types/qaTaskResponse'

// Reads the files off the row, which already embeds them.
const props = defineProps<{ files: QaEvidenceFile[] }>()
const emit = defineEmits<{ preview: [file: QaEvidenceFile] }>()

const { t } = useI18n()

// A measurement report is a PDF or a photo; the icon says which, so an
// inspector can tell a scan from a snap without opening it.
const decorated = computed(() =>
  props.files.map((file) => ({
    file,
    icon: file.mime_type.startsWith('image/') ? 'mdi-file-image' : 'mdi-file-pdf-box',
    isImage: file.mime_type.startsWith('image/'),
  })),
)
</script>

<template>
  <div class="qa-evidence-cell">
    <i
      v-for="{ file, icon, isImage } in decorated"
      :key="file.id"
      class="mdi evidence-icon"
      :class="[icon, isImage ? 'icon-image' : 'icon-pdf']"
      role="button"
      tabindex="0"
      v-tooltip.focus="t('productionQa.evidence.openFile', { name: file.file_name })"
      :aria-label="t('productionQa.evidence.openFile', { name: file.file_name })"
      @click.stop="emit('preview', file)"
      @keydown.enter="emit('preview', file)"
      @keydown.space.prevent="emit('preview', file)"
    />
  </div>
</template>

<style scoped lang="scss">
.qa-evidence-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: nowrap;
  // Sized for a handful of icons; more scrolls rather than wraps.
  overflow-x: auto;
  scrollbar-width: none;
}

.evidence-icon {
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

.icon-pdf {
  color: var(--p-red-500);
}

.icon-image {
  color: var(--p-blue-500);
}
</style>
