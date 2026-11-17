<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useClipboard } from '@/core/composables/useClipboard'
import { formatDecimal } from '@/core/utils/numbers'
import { safeHref } from '@/shared/utils/isSafeHttpUrl'
import { catalogueStatusSeverity } from '../../utils/catalogueStatus'
import { useHostStore } from '@/core/host/stores/hostStore'
import { getMadeItemChangelog } from '@/features/made-items'
import { getMadeItemFileBlob } from '@/features/made-items'
import { useMadeItemFilesStore } from '@/features/made-items'
import { useMadeItemPicturesStore } from '@/features/made-items'
import { useShownPicture } from '@/shared/pictures'
import { MadeItemThumbnailCell } from '@/features/made-items'
import { useMadeItemLabel } from '@/features/made-items'
import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'
import { useBlobObjectUrl } from '@/shared/composables/useBlobObjectUrl'
import { useChangedByUser } from '../../composables/useChangedByUser'
import LotRecordMeta from './LotRecordMeta.vue'

import type { LotResponse } from '../../../types/productionLotsResponse'
import type { MadeItemFile, MadeItemResponse } from '@/features/made-items'
import type { MadeItemChangelogEntry } from '@/features/made-items'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import LabelTag from '@/shared/components/labels/LabelTag.vue'
import { localizeLabel } from '@/shared/utils/localizeLabel'

// Loads the three.js viewer only for items with a mesh.
const MeshViewer = defineAsyncComponent(() => import('@/core/components/MeshViewer.vue'))

const FILE_CATEGORY_ICON: Record<string, string> = {
  image: 'mdi-image-outline',
  step: 'mdi-file-outline',
  mesh: 'mdi-cube-outline',
  pdf: 'mdi-file-pdf-box',
}

const props = defineProps<{
  lot: LotResponse
  madeItem: MadeItemResponse | null
}>()

defineEmits<{ 'view-item': [] }>()

const { t } = useI18n()
const { copyToClipboard } = useClipboard()
const hostStore = useHostStore()
const { format: madeItemLabel } = useMadeItemLabel()
const filesStore = useMadeItemFilesStore()

const processes = computed(() =>
  props.madeItem
    ? [...(props.madeItem.processes ?? [])]
        .sort((a, b) => a.position - b.position)
        .map((p) => localizeLabel(p.fabrication_method_name))
        .join(', ')
    : '',
)

const changelogEntries = ref<MadeItemChangelogEntry[]>([])

watch(
  () => props.madeItem?.id ?? null,
  async (id) => {
    changelogEntries.value = []
    if (id === null) return
    changelogEntries.value = await getMadeItemChangelog(id)
  },
  { immediate: true },
)

const { resolve } = useChangedByUser()
const changedBy = computed(() => resolve(changelogEntries.value))

if (hostStore.storageEnabled) {
  void filesStore.fetchFiles(props.lot.made_item_id)
}

const visibleFiles = computed(() => filesStore.getFiles(props.lot.made_item_id))

// What the thumbnail box opens: the full-size picture shown for the item.
const shownPicture = useShownPicture(useMadeItemPicturesStore(), () => props.lot.made_item_id)

const meshFile = computed(() => visibleFiles.value.find((f) => f.category === 'mesh') ?? null)
const meshBlob = ref<Blob | null>(null)
const meshLoading = ref(false)

watch(
  () => meshFile.value?.id ?? null,
  async (fileId) => {
    meshBlob.value = null
    if (fileId === null || !meshFile.value) return
    meshLoading.value = true
    try {
      meshBlob.value = await getMadeItemFileBlob(props.lot.made_item_id, fileId)
    } finally {
      meshLoading.value = false
    }
  },
  { immediate: true },
)

// The PDF drawing is previewed through an object URL in the browser viewer.
const drawingFile = computed(() => visibleFiles.value.find((f) => f.category === 'drawing') ?? null)
const { url: drawingUrl, loading: drawingLoading } = useBlobObjectUrl(
  () => drawingFile.value?.id ?? null,
  (fileId) => getMadeItemFileBlob(props.lot.made_item_id, fileId),
)

interface PreviewTarget {
  name: string
  mimeType: string
  fetch: () => Promise<Blob>
}

const previewFile = ref<PreviewTarget | null>(null)
const showFilePreview = ref(false)

function openFile(file: MadeItemFile): void {
  const itemId = props.lot.made_item_id
  previewFile.value = {
    name: file.file_name,
    mimeType: file.mime_type,
    fetch: () => getMadeItemFileBlob(itemId, file.id),
  }
  showFilePreview.value = true
}

function openPicture(): void {
  const picture = shownPicture.value
  if (!picture) return
  previewFile.value = { name: picture.name, mimeType: 'image/*', fetch: picture.fetchImage }
  showFilePreview.value = true
}

// The mesh tile is also an orbit surface, so a drag that happens to end
// inside it must not count as a click that opens the dialog.
let pointerStart: { x: number; y: number } | null = null

function onMeshPointerDown(event: PointerEvent): void {
  pointerStart = { x: event.clientX, y: event.clientY }
}

function onMeshClick(event: MouseEvent): void {
  const start = pointerStart
  pointerStart = null
  if (start && Math.hypot(event.clientX - start.x, event.clientY - start.y) > 4) return
  if (meshFile.value) openFile(meshFile.value)
}

function fetchPreviewBlob(): Promise<Blob> {
  const target = previewFile.value
  if (!target) return Promise.reject(new Error('No file selected.'))
  return target.fetch()
}

// A weblink becomes a link only when it is an absolute http(s) URL; any other stored value shows as text.
const weblinkHref = computed(() => safeHref(props.madeItem?.weblink))
</script>

<template>
  <Panel
    :header="t('production.lots.detail.record.item.title')"
    :pt="{ header: { 'data-testid': 'record-card-header' } }"
  >
    <!-- The creator/changer footer scrolls with the fields, so it never
         reserves card height of its own; margin-top: auto still puts it at
         the bottom when the fields are short. -->
    <div class="card-scroll-body card-scroll-body--with-meta">
      <div class="item-layout">
        <div v-if="hostStore.storageEnabled" class="item-media">
          <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a button only while there is something to open, the role and tabindex are bound to that -->
          <div
            class="thumb-box"
            :class="{ 'media-clickable': !!shownPicture }"
            :role="shownPicture ? 'button' : undefined"
            :tabindex="shownPicture ? 0 : undefined"
            v-tooltip="
              shownPicture
                ? t('production.lots.detail.record.item.openFile', { name: shownPicture.name })
                : undefined
            "
            @click="openPicture"
            @keydown.enter="openPicture"
          >
            <MadeItemThumbnailCell
              :item-id="lot.made_item_id"
              :item-name="lot.made_item_article_name"
              size="6rem"
              no-image-icon="mdi mdi-image-off-outline"
            />
          </div>

          <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a button only while there is something to open, the role and tabindex are bound to that -->
          <div
            v-if="meshLoading || meshBlob"
            class="media-tile"
            :class="{ 'media-clickable': !!meshFile }"
            :role="meshFile ? 'button' : undefined"
            :tabindex="meshFile ? 0 : undefined"
            v-tooltip="
              meshFile
                ? t('production.lots.detail.record.item.openFile', { name: meshFile.file_name })
                : undefined
            "
            @pointerdown="onMeshPointerDown"
            @click="onMeshClick"
            @keydown.enter="meshFile && openFile(meshFile)"
          >
            <i v-if="meshLoading" class="mdi mdi-loading mdi-spin" aria-hidden="true" />
            <MeshViewer v-else-if="meshBlob" :blob="meshBlob" />
          </div>

          <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a button only while there is something to open, the role and tabindex are bound to that -->
          <div
            v-if="drawingLoading || drawingUrl"
            class="media-tile media-tile--drawing"
            :class="{ 'media-clickable': !!drawingFile }"
            :role="drawingFile ? 'button' : undefined"
            :tabindex="drawingFile ? 0 : undefined"
            v-tooltip="
              drawingFile
                ? t('production.lots.detail.record.item.openFile', { name: drawingFile.file_name })
                : undefined
            "
            @click="drawingFile && openFile(drawingFile)"
            @keydown.enter="drawingFile && openFile(drawingFile)"
          >
            <i v-if="drawingLoading" class="mdi mdi-loading mdi-spin" aria-hidden="true" />
            <!-- Rendered at full size and scaled down, since the PDF viewer needs a
                 usable viewport. Pointer events are off so the tile takes the click. -->
            <iframe
              v-else-if="drawingUrl"
              :src="`${drawingUrl}#toolbar=0&navpanes=0&scrollbar=0&view=FitV`"
              class="drawing-frame"
              :title="drawingFile?.file_name"
              tabindex="-1"
            />
          </div>
        </div>

        <div class="detail-grid">
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.item.partNumber')
            }}</span>
            <span class="field-value">{{
              madeItemLabel(lot.made_item_part_number, lot.made_item_revision)
            }}</span>
          </div>
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.item.articleName')
            }}</span>
            <span
              class="field-value field-link"
              role="button"
              tabindex="0"
              @click="$emit('view-item')"
              @keydown.enter="$emit('view-item')"
              >{{ lot.made_item_article_name }}</span
            >
          </div>
          <div class="field">
            <span class="field-label">{{ t('production.lots.detail.record.item.revision') }}</span>
            <span class="field-value">{{ lot.made_item_revision || getEmptyPlaceholder() }}</span>
          </div>
          <div class="field">
            <span class="field-label">{{ t('production.lots.detail.record.item.material') }}</span>
            <span class="field-value">{{ madeItem?.material ?? getEmptyPlaceholder() }}</span>
          </div>
          <div class="field">
            <span class="field-label">{{ t('production.lots.detail.record.item.mass') }}</span>
            <span class="field-value">{{ formatDecimal(madeItem?.mass) }}</span>
          </div>
          <div class="field">
            <span class="field-label">{{ t('production.lots.detail.record.item.baseSize') }}</span>
            <span class="field-value">{{ madeItem?.base_size ?? getEmptyPlaceholder() }}</span>
          </div>
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.item.revisionDate')
            }}</span>
            <span class="field-value">{{ madeItem?.revision_date ?? getEmptyPlaceholder() }}</span>
          </div>
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.item.dataSource')
            }}</span>
            <span class="field-value">{{
              madeItem?.data_source
                ? t(`madeItems.catalogue.dataSources.${madeItem.data_source}`)
                : getEmptyPlaceholder()
            }}</span>
          </div>
          <div class="field">
            <span class="field-label">{{ t('production.lots.detail.record.item.status') }}</span>
            <Tag
              v-if="madeItem"
              :value="t(`production.lots.detail.record.item.statusValues.${madeItem.status}`)"
              :severity="catalogueStatusSeverity[madeItem.status]"
            />
            <span v-else class="field-value">{{ getEmptyPlaceholder() }}</span>
          </div>
          <div v-if="madeItem?.successor_item_id != null" class="field">
            <span class="field-label">{{ t('production.lots.detail.record.item.successor') }}</span>
            <span class="field-value">#{{ madeItem.successor_item_id }}</span>
          </div>
          <div v-if="madeItem?.article_groups?.length" class="field field-wide">
            <span class="field-label">{{
              t('production.lots.detail.record.item.articleGroups')
            }}</span>
            <div class="groups">
              <LabelTag
                v-for="group in madeItem.article_groups"
                :key="group.id"
                :label="group"
              />
            </div>
          </div>
          <div v-if="madeItem?.revision_note" class="field field-wide">
            <span class="field-label">{{
              t('production.lots.detail.record.item.revisionNote')
            }}</span>
            <span class="field-value field-multiline">{{ madeItem.revision_note }}</span>
          </div>
          <div v-if="processes" class="field field-wide">
            <span class="field-label">{{ t('production.lots.detail.record.item.processes') }}</span>
            <span class="field-value">{{ processes }}</span>
          </div>
          <div v-if="madeItem?.weblink" class="field field-wide">
            <span class="field-label">{{ t('production.lots.detail.record.item.weblink') }}</span>
            <a
              v-if="weblinkHref"
              :href="weblinkHref"
              target="_blank"
              rel="noopener noreferrer"
              class="field-value field-link field-break"
              >{{ madeItem.weblink }}</a
            >
            <span v-else class="field-value field-break">{{ madeItem.weblink }}</span>
          </div>
          <div class="field field-wide">
            <span class="field-label">{{ t('production.lots.detail.record.item.note') }}</span>
            <span class="field-value field-multiline">{{
              madeItem?.note || getEmptyPlaceholder()
            }}</span>
          </div>
          <div v-if="madeItem" class="field field-wide">
            <span class="field-label">{{ t('production.lots.detail.record.item.publicId') }}</span>
            <span
              class="field-value field-uuid field-link"
              role="button"
              tabindex="0"
              v-tooltip.top="t('common.copyUuid')"
              @click="copyToClipboard(madeItem.public_id)"
              @keydown.enter="copyToClipboard(madeItem.public_id)"
              >{{ madeItem.public_id }}</span
            >
          </div>
          <div v-if="madeItem?.archived" class="field field-wide">
            <Tag :value="t('common.archivedTag')" severity="warn" icon="mdi mdi-archive-outline" />
          </div>
        </div>
      </div>

      <div v-if="visibleFiles.length" class="item-files">
        <i
          v-for="file in visibleFiles"
          :key="file.id"
          class="mdi item-file-icon"
          :class="FILE_CATEGORY_ICON[file.category] ?? 'mdi-file-outline'"
          role="button"
          tabindex="0"
          v-tooltip.focus="t('production.lots.detail.record.item.openFile', { name: file.file_name })"
          :aria-label="t('production.lots.detail.record.item.openFile', { name: file.file_name })"
          @click="openFile(file)"
          @keydown.enter="openFile(file)"
          @keydown.space.prevent="openFile(file)"
        />
      </div>

      <LotRecordMeta
        v-if="madeItem"
        :creator="madeItem.creator"
        :created="madeItem.created"
        :changed="madeItem.changed"
        :changed-by="changedBy"
      />
    </div>

    <FilePreviewDialog
      v-if="previewFile"
      v-model:visible="showFilePreview"
      :filename="previewFile.name"
      :mime-type="previewFile.mimeType"
      :fetch-blob="fetchPreviewBlob"
    />
  </Panel>
</template>

<style scoped lang="scss">
.item-layout {
  display: flex;
  gap: var(--space-4);
  align-items: flex-start;
}

.item-media {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  flex-shrink: 0;
}

.media-tile {
  width: 6rem;
  height: 6rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--p-border-radius-sm);
  border: 1px solid var(--p-content-border-color);
  overflow: hidden;
}

// The scaled iframe still claims its untransformed size in flow, so it is
// taken out of it and pinned to the tile's top-left corner.
.media-tile--drawing {
  position: relative;
  background: var(--p-content-hover-background);
}

// 30rem scaled by 0.22 is 6.6rem in a 6rem tile, so the offset re-centres the
// 0.3rem that overhangs each edge. The overscan swallows the margin the
// embedded viewer keeps around the page, which would otherwise show as a dark
// band; view=FitV crops the drawing's sides instead of letterboxing it.
.drawing-frame {
  position: absolute;
  top: -0.3rem;
  left: -0.3rem;
  width: 30rem;
  height: 30rem;
  border: none;
  transform: scale(0.22);
  transform-origin: top left;
  pointer-events: none;
}

.thumb-box {
  border-radius: var(--p-border-radius-sm);
}

.media-clickable {
  cursor: pointer;

  &:hover {
    border-color: var(--p-primary-color);
  }

  &:hover :deep(.thumb-img),
  &:hover :deep(.thumb-empty) {
    border-color: var(--p-primary-color);
  }
}

.detail-grid {
  flex: 1;
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
  gap: var(--space-3) var(--space-5);
}

.field {
  min-width: 0;
}

.field-wide {
  grid-column: 1 / -1;
}

.field-value {
  font-size: var(--font-size-sm);
}

.field-sublabel {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.field-multiline {
  white-space: pre-line;
}

.field-break {
  overflow-wrap: anywhere;
}

.field-uuid {
  font-family: monospace;
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.field-link {
  cursor: pointer;
  width: fit-content;
  color: inherit;
  text-decoration: none;

  &:hover {
    color: var(--p-primary-color);
    text-decoration: underline;
  }
}

.groups {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.item-files {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-top: var(--space-3);
}

.item-file-icon {
  font-size: var(--font-size-xl);
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
