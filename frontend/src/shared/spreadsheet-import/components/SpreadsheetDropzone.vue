<script setup lang="ts">
// The upload step of a spreadsheet import: a drop zone that also opens the
// file picker, emitting the chosen Excel file.
import { ref } from 'vue'

defineProps<{
  label: string
  hint: string
  loading?: boolean
}>()

const emit = defineEmits<{
  file: [file: File]
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const isDraggingOver = ref(false)

function openFilePicker(): void {
  fileInput.value?.click()
}

function onFileSelected(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (file) emit('file', file)
}

function onDrop(event: DragEvent): void {
  isDraggingOver.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) emit('file', file)
}

defineExpose({ openFilePicker })
</script>

<template>
  <input
    ref="fileInput"
    type="file"
    aria-hidden="true"
    tabindex="-1"
    accept=".xlsx,.xls"
    class="hidden-file-input"
    data-testid="spreadsheet-file-input"
    @change="onFileSelected"
  />
  <div
    class="dropzone"
    :class="{ 'dropzone-active': isDraggingOver }"
    role="button"
    tabindex="0"
    :aria-label="label"
    @click="openFilePicker"
    @keydown.enter="openFilePicker"
    @keydown.space.prevent="openFilePicker"
    @dragover.prevent="isDraggingOver = true"
    @dragenter.prevent="isDraggingOver = true"
    @dragleave.prevent="isDraggingOver = false"
    @drop.prevent="onDrop"
  >
    <i class="mdi mdi-file-excel-outline dropzone-icon" aria-hidden="true" />
    <p>{{ hint }}</p>
    <Button :label="label" icon="mdi mdi-upload" :loading="loading" @click.stop="openFilePicker" />
  </div>
</template>

<style scoped lang="scss">
.hidden-file-input {
  display: none;
}

.dropzone {
  flex: 1 1 0%;
  min-height: 16rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  border: 2px dashed var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  cursor: pointer;
  transition:
    border-color 0.15s,
    background-color 0.15s;

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: -2px;
  }
}

.dropzone:hover {
  border-color: var(--p-primary-color);
}

.dropzone-active {
  border-color: var(--p-primary-color);
  background: var(--p-highlight-bg);
}

.dropzone-icon {
  font-size: var(--font-size-4xl);
  color: var(--p-text-muted-color);
}
</style>
