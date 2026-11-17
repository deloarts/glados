<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { extractApiError } from '@/core/utils/errors'
import { formatBytes } from '@/core/utils/bytes'
import { isPreviewableFile } from '@/core/utils/meshFile'
import { downloadOrderAttachment } from '../api/downloadOrderAttachment'
import { getOrderFileBlob } from '../api/getOrderFileBlob'
import { useOrderFilesStore } from '../stores/orderFilesStore'
import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import type { OrderFileCategory, OrderResponse } from '../types/ordersResponse'
import type { OrderFile } from '../types/ordersResponse'

const ORDER_FILE_CATEGORIES: OrderFileCategory[] = [
  'proposal',
  'order_confirmation',
  'delivery_note',
  'invoice',
  'general',
  'picture',
]

const props = defineProps<{
  order: OrderResponse
  canWrite: boolean
}>()

const { t } = useI18n()
const filesStore = useOrderFilesStore()
const { missing } = useMissingPermission()
// canWrite is write:orders; without it Delete stays visible but disabled.
const writeBlocked = computed(() => (props.canWrite ? '' : missing(Permission.WRITE_ORDERS)))

const files = computed(() => filesStore.getFiles(props.order.id))

const isDragOver = ref(false)
const dragOverCategory = ref<OrderFileCategory | null>(null)
const uploadingCategories = ref<Set<OrderFileCategory>>(new Set())
const uploadErrors = ref<Map<OrderFileCategory, string>>(new Map())
const deletingIds = ref<Set<number>>(new Set())
const popoverRef = ref()

const previewFile = ref<OrderFile | null>(null)
const showPreview = ref(false)

onMounted(() => {
  void filesStore.fetchFiles(props.order.id)
})

function filesForCategory(cat: OrderFileCategory): OrderFile[] {
  return files.value.filter((f) => f.category === cat)
}

// Categories with nothing to say are dropped rather than dimmed. An
// in-flight upload or a failed one still needs a badge to show it, even
// with zero files landed yet.
const visibleCategories = computed(() =>
  ORDER_FILE_CATEGORIES.filter(
    (cat) =>
      filesForCategory(cat).length > 0 ||
      uploadingCategories.value.has(cat) ||
      uploadErrors.value.has(cat),
  ),
)

// ── Drag & drop ────────────────────────────────────────────────────────

function onDragEnter(e: DragEvent): void {
  e.preventDefault()
  isDragOver.value = true
}

function onDragOver(e: DragEvent): void {
  e.preventDefault()
}

function onDragLeave(e: DragEvent): void {
  const related = e.relatedTarget as Node | null
  if (related && (e.currentTarget as HTMLElement).contains(related)) return
  isDragOver.value = false
  dragOverCategory.value = null
}

function onCategoryDragEnter(cat: OrderFileCategory): void {
  dragOverCategory.value = cat
}

function onCategoryDragLeave(): void {
  dragOverCategory.value = null
}

async function onCategoryDrop(e: DragEvent, cat: OrderFileCategory): Promise<void> {
  e.preventDefault()
  isDragOver.value = false
  dragOverCategory.value = null
  if (!props.canWrite) return

  const file = e.dataTransfer?.files[0]
  if (!file) return

  await doUpload(file, cat)
}

async function doUpload(file: File, category: OrderFileCategory): Promise<void> {
  uploadingCategories.value = new Set([...uploadingCategories.value, category])
  const errs = new Map(uploadErrors.value)
  errs.delete(category)
  uploadErrors.value = errs
  try {
    await filesStore.upload(props.order.id, file, category)
  } catch (e) {
    const next = new Map(uploadErrors.value)
    next.set(category, extractApiError(e) ?? t('orders.files.errors.upload'))
    uploadErrors.value = next
  } finally {
    uploadingCategories.value = new Set(
      [...uploadingCategories.value].filter((c) => c !== category),
    )
  }
}

// ── Popover (file list) ────────────────────────────────────────────────

function openFileList(e: Event): void {
  popoverRef.value?.toggle(e)
}

async function onDownload(f: OrderFile): Promise<void> {
  await downloadOrderAttachment(props.order.id, f.id, f.file_name)
}

function openPreview(f: OrderFile): void {
  previewFile.value = f
  showPreview.value = true
}

function fetchPreviewBlob(): Promise<Blob> {
  if (!previewFile.value) return Promise.reject(new Error('No file selected.'))
  return getOrderFileBlob(props.order.id, previewFile.value.id)
}

async function onDelete(f: OrderFile): Promise<void> {
  deletingIds.value = new Set([...deletingIds.value, f.id])
  try {
    await filesStore.remove(props.order.id, f.id)
  } finally {
    deletingIds.value = new Set([...deletingIds.value].filter((id) => id !== f.id))
  }
}

// The template root is a single element, so a disable comment in front
// of it would turn the root into a fragment and stop attribute fallthrough.
/* eslint-disable vuejs-accessibility/no-static-element-interactions -- the cell and its category zones are drop targets for dragged files, the order's files panel is the keyboard path */
</script>

<template>
  <div
    class="files-cell"
    :class="{ 'drag-active': isDragOver }"
    @dragenter="onDragEnter"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
  >
    <!-- Compact category badges. No spinner, since every row fetches on its own
         and spinners would flash across the table; files pop in once loaded. -->
    <template v-if="!isDragOver">
      <div class="files-summary">
        <div
          v-for="cat in visibleCategories"
          :key="cat"
          class="category-badge"
          :class="[`cat-${cat}`, { 'has-files': filesForCategory(cat).length > 0 }]"
          role="button"
          tabindex="0"
          :aria-disabled="filesForCategory(cat).length === 0 || undefined"
          v-tooltip.top="t(`orders.files.categories.${cat}`)"
          @click.stop="(e: MouseEvent) => filesForCategory(cat).length > 0 && openFileList(e)"
          @keydown.enter.space.prevent.stop="(e: KeyboardEvent) => filesForCategory(cat).length > 0 && openFileList(e)"
        >
          <span class="cat-label">{{ t(`orders.files.categoryShort.${cat}`) }}</span>
          <span v-if="filesForCategory(cat).length > 0" class="cat-count">
            {{ filesForCategory(cat).length }}
          </span>
          <i
            v-if="uploadingCategories.has(cat)"
            class="mdi mdi-loading mdi-spin cat-spinner"
            aria-hidden="true"
          />
          <i
            v-else-if="uploadErrors.has(cat)"
            class="mdi mdi-alert-circle-outline cat-error"
            aria-hidden="true"
            v-tooltip="uploadErrors.get(cat)"
          />
        </div>
      </div>
    </template>

    <!-- Drag-over state: show category drop zones -->
    <template v-else>
      <div class="drop-zones">
        <div
          v-for="cat in ORDER_FILE_CATEGORIES"
          :key="cat"
          class="drop-zone"
          :class="[`cat-${cat}`, { 'drop-zone-active': dragOverCategory === cat }]"
          @dragenter.stop="onCategoryDragEnter(cat)"
          @dragleave.stop="onCategoryDragLeave"
          @drop.stop="onCategoryDrop($event, cat)"
        >
          {{ t(`orders.files.categoryShort.${cat}`) }}
        </div>
      </div>
    </template>
  </div>

  <!-- File list popover -->
  <Popover
    ref="popoverRef"
    append-to="body"
    :pt="{ content: { style: 'padding: 0.1rem 0.75rem' } }"
  >
    <div class="file-popover">
      <div v-for="cat in ORDER_FILE_CATEGORIES" :key="cat">
        <template v-if="filesForCategory(cat).length > 0">
          <div class="popover-category-label">
            {{ t(`orders.files.categories.${cat}`) }}
          </div>
          <div v-for="f in filesForCategory(cat)" :key="f.id" class="popover-file-row">
            <i class="mdi mdi-file-outline" aria-hidden="true" />
            <span class="popover-file-name" :title="f.file_name">{{ f.file_name }}</span>
            <span class="popover-file-size">{{ formatBytes(f.size_bytes) }}</span>
            <Button
              v-if="isPreviewableFile(f.file_name, f.mime_type)"
              icon="mdi mdi-eye-outline"
              size="small"
              text
              rounded
              severity="secondary"
              v-tooltip.focus="t('common.files.preview')"
              :aria-label="t('common.files.preview')"
              @click="openPreview(f)"
            />
            <Button
              icon="mdi mdi-download-outline"
              size="small"
              text
              rounded
              severity="secondary"
              v-tooltip.focus="t('orders.files.download')"
              :aria-label="t('orders.files.download')"
              @click="onDownload(f)"
            />
            <span v-tooltip.top="writeBlocked || undefined">
              <Button
                icon="mdi mdi-delete-outline"
                size="small"
                text
                rounded
                severity="danger"
                :disabled="!canWrite"
                :loading="deletingIds.has(f.id)"
                v-tooltip.focus="t('orders.files.delete')"
                :aria-label="t('orders.files.delete')"
                data-testid="order-file-delete"
                @click="onDelete(f)"
              />
            </span>
          </div>
        </template>
      </div>
    </div>
  </Popover>

  <FilePreviewDialog
    v-if="previewFile"
    v-model:visible="showPreview"
    :filename="previewFile.file_name"
    :mime-type="previewFile.mime_type"
    :fetch-blob="fetchPreviewBlob"
  />
</template>

<style scoped lang="scss">
.files-cell {
  display: flex;
  align-items: center;
  min-height: 2rem;
  padding: var(--space-1) var(--space-1);
  border-radius: var(--p-border-radius-sm);
  overflow: hidden;
  transition: background 0.15s;

  &.drag-active {
    background: var(--p-primary-50, color-mix(in srgb, var(--p-primary-color) 8%, transparent));
    outline: 2px dashed var(--p-primary-color);
    outline-offset: -2px;
    padding: var(--space-1);
  }
}

.files-summary {
  display: flex;
  flex-wrap: nowrap;
  gap: var(--space-1);
  overflow: hidden;
}

.category-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-1);
  border-radius: 1rem;
  font-size: var(--font-size-xs);
  font-weight: 500;
  // Lower values were unreadable in dark mode.
  opacity: 0.5;
  border: 1px solid currentColor;
  white-space: nowrap;
  user-select: none;

  &.has-files {
    opacity: 1;
    cursor: pointer;

    &:hover {
      filter: brightness(0.9);
    }
  }

  &.cat-proposal {
    color: var(--p-blue-500);
    border-color: var(--p-blue-200);
  }
  &.cat-order_confirmation {
    color: var(--p-green-600);
    border-color: var(--p-green-200);
  }
  &.cat-delivery_note {
    color: var(--p-orange-500);
    border-color: var(--p-orange-200);
  }
  &.cat-invoice {
    color: var(--p-indigo-500);
    border-color: var(--p-indigo-200);
  }
  &.cat-general {
    color: var(--p-text-muted-color);
    border-color: var(--p-content-border-color);
  }
  &.cat-picture {
    color: var(--p-purple-500);
    border-color: var(--p-purple-200);
  }
}

.cat-count {
  background: currentColor;
  color: var(--on-accent);
  border-radius: 1rem;
  padding: 0 var(--space-1);
  font-size: var(--font-size-xs);
  line-height: 1.4;
}

.cat-spinner,
.cat-error {
  font-size: var(--font-size-xs);
}
.cat-error {
  color: var(--p-red-500);
}

// ── Drop zones ─────────────────────────────────────────────────────────

.drop-zones {
  display: flex;
  gap: var(--space-1);
  width: 100%;
}

.drop-zone {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-1) var(--space-1);
  border-radius: var(--p-border-radius-sm);
  border: 1.5px dashed currentColor;
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-align: center;
  transition: background 0.1s;
  cursor: copy;

  &.cat-proposal {
    color: var(--p-blue-500);
  }
  &.cat-order_confirmation {
    color: var(--p-green-600);
  }
  &.cat-delivery_note {
    color: var(--p-orange-500);
  }
  &.cat-invoice {
    color: var(--p-indigo-500);
  }
  &.cat-general {
    color: var(--p-text-muted-color);
  }
  &.cat-picture {
    color: var(--p-purple-500);
  }

  &.drop-zone-active {
    &.cat-proposal {
      background: color-mix(in srgb, var(--p-blue-500) 15%, transparent);
    }
    &.cat-order_confirmation {
      background: color-mix(in srgb, var(--p-green-600) 15%, transparent);
    }
    &.cat-delivery_note {
      background: color-mix(in srgb, var(--p-orange-500) 15%, transparent);
    }
    &.cat-invoice {
      background: color-mix(in srgb, var(--p-indigo-500) 15%, transparent);
    }
    &.cat-general {
      background: var(--p-content-hover-background);
    }
    &.cat-picture {
      background: color-mix(in srgb, var(--p-purple-500) 15%, transparent);
    }
  }
}

// ── Popover ────────────────────────────────────────────────────────────

.file-popover {
  min-width: 18rem;
  max-width: 26rem;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.popover-category-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
  padding: var(--space-1) 0 var(--space-1);
}

.popover-file-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  padding: var(--space-1) 0;

  i:first-child {
    color: var(--p-text-muted-color);
    flex-shrink: 0;
  }
}

.popover-file-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.popover-file-size {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}
</style>
