<script setup lang="ts">
import { computed, defineAsyncComponent, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { isMeshFile } from '@/core/utils/meshFile'
import { downloadBlob } from '@/core/utils/downloadBlob'
import { withMimeFallback } from '@/core/utils/blobMime'
import { pdfFitUrl } from '@/core/utils/pdfEmbed'

const MeshViewer = defineAsyncComponent(() => import('./MeshViewer.vue'))

const props = defineProps<{
  filename: string
  mimeType: string
  fetchBlob: () => Promise<Blob>
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const { toastOnError } = useErrorToast()

const blob = ref<Blob | null>(null)
const blobUrl = ref<string | null>(null)
const loading = ref(false)
const iframeLoading = ref(false)
const error = ref<string | null>(null)

// OpenVue's own .p-dialog-maximized CSS rule sets width/height to
// 100vw/100vh with !important, which does beat an inline style, but only
// for the properties it actually declares. It never touches max-width, so
// the dialog's own inline `maxWidth: '1200px'` below stayed in effect
// uncontested while maximized, capping the width even though height
// expanded freely (an !important height rule with nothing competing).
// Tracking the maximized state and dropping every dimension from the
// inline style while it's true (rather than only overriding max-width)
// leaves the CSS rule as the single source of truth for every dimension,
// with nothing left to fight it, in either direction.
const isMaximized = ref(false)

const dialogStyle = computed(() =>
  isMaximized.value
    ? undefined
    : { width: 'var(--dialog-width-full)', maxWidth: '1200px', height: '92vh' },
)

const isImage = computed(() => props.mimeType.startsWith('image/'))
const isPdf = computed(() => props.mimeType === 'application/pdf')

// Opened to fit the page, whatever zoom the viewer used last (pdfFitUrl).
const pdfSrc = computed(() => (blobUrl.value ? pdfFitUrl(blobUrl.value) : null))
const isMesh = computed(() => isMeshFile(props.filename, props.mimeType))
const isPreviewable = computed(() => isImage.value || isPdf.value || isMesh.value)

watch(
  visible,
  async (open) => {
    if (open && isPreviewable.value) {
      await loadBlob()
    } else if (!open) {
      cleanup()
    }
  },
  { immediate: true },
)

onUnmounted(cleanup)

async function loadBlob(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const fetched = await props.fetchBlob()
    blob.value = fetched
    if (!isMesh.value) {
      blobUrl.value = URL.createObjectURL(withMimeFallback(fetched, props.mimeType))
      if (isPdf.value) iframeLoading.value = true
    }
  } catch {
    error.value = t('common.filePreview.error')
  } finally {
    loading.value = false
  }
}

function cleanup(): void {
  if (blobUrl.value) {
    URL.revokeObjectURL(blobUrl.value)
    blobUrl.value = null
  }
  blob.value = null
  error.value = null
  loading.value = false
  iframeLoading.value = false
}

function download(): void {
  if (blob.value) {
    downloadBlob(blob.value, props.filename)
  } else {
    props
      .fetchBlob()
      .then((fetched) => downloadBlob(fetched, props.filename))
      .catch(toastOnError(t('common.filePreview.downloadFailed')))
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    :header="filename"
    modal
    maximizable
    :style="dialogStyle"
    :pt="{
      content: {
        style: 'padding: 0; flex: 1; display: flex; flex-direction: column; overflow: hidden;',
      },
    }"
    @maximize="isMaximized = true"
    @unmaximize="isMaximized = false"
    @hide="isMaximized = false"
  >
    <div class="preview-body">
      <div v-if="loading" class="preview-state">
        <i class="mdi mdi-loading mdi-spin preview-state-icon" aria-hidden="true" />
        <span>{{ t('common.filePreview.loading') }}</span>
      </div>

      <div v-else-if="error" class="preview-state preview-state--error">
        <i class="mdi mdi-alert-circle-outline preview-state-icon" aria-hidden="true" />
        <span>{{ error }}</span>
      </div>

      <div v-else-if="!isPreviewable" class="preview-state">
        <i class="mdi mdi-file-off-outline preview-state-icon" aria-hidden="true" />
        <span>{{ t('common.filePreview.unsupported') }}</span>
        <span class="preview-mime">{{ mimeType }}</span>
      </div>

      <MeshViewer v-else-if="isMesh && blob" :blob="blob" />

      <img v-else-if="blobUrl && isImage" :src="blobUrl" class="preview-image" :alt="filename" />

      <!-- iframe must be in the DOM as soon as blobUrl is set so @load can fire.
           iframeLoading is kept local here, if it were in the top-level v-if the spinner
           would win, the iframe would never mount, and @load would never fire. -->
      <template v-else-if="blobUrl">
        <div v-if="iframeLoading" class="preview-state">
          <i class="mdi mdi-loading mdi-spin preview-state-icon" aria-hidden="true" />
          <span>{{ t('common.filePreview.loading') }}</span>
        </div>
        <iframe
          v-show="!iframeLoading"
          :src="pdfSrc ?? blobUrl"
          class="preview-iframe"
          :title="filename"
          @load="iframeLoading = false"
        />
      </template>
    </div>

    <template #footer>
      <div class="preview-footer">
        <span class="preview-footer-meta">{{ mimeType }} &middot; {{ filename }}</span>
        <Button
          :label="t('common.filePreview.download')"
          icon="mdi mdi-download-outline"
          severity="secondary"
          @click="download"
        />
      </div>
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
// The dialog has a fixed height, so the body and its content fill it rather
// than asserting a min-height of their own.
.preview-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.preview-iframe {
  flex: 1;
  width: 100%;
  height: 100%;
  border: none;
  min-height: 0;
}

.preview-image {
  flex: 1;
  width: 100%;
  height: 100%;
  object-fit: contain;
  min-height: 0;
  background: var(--p-content-hover-background);
}

.preview-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
  padding: var(--space-6);

  &--error {
    color: var(--p-red-500);
  }
}

.preview-state-icon {
  font-size: var(--font-size-4xl);
  opacity: 0.5;
}

.preview-mime {
  font-size: var(--font-size-xs);
  opacity: 0.6;
}

.preview-footer {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  width: 100%;
  padding-top: var(--space-2);
}

.preview-footer-meta {
  flex: 1;
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
